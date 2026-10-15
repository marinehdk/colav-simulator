"""Real TCP lifecycle regression; run inside gst-base with python3 -m unittest.

GStreamer is imported from the same runtime as the sender. The GLib dispatcher
is controlled so callbacks from a retired connection can run after reconnect.
"""
import importlib.util
from pathlib import Path
import queue
import socket
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "twin_sender", Path(__file__).resolve().parents[1] / "sender" / "sender.py"
)
sender_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sender_module)


class SenderBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sender_module.Gst.init(None)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(8)
        self.server.settimeout(1)
        self.peers = []
        self.callbacks = queue.Queue()
        self.dispatch = patch.object(
            sender_module.GLib, "idle_add",
            side_effect=lambda fn, *args: self.callbacks.put((fn, args)),
        )
        self.dispatch.start()
        self.sender = sender_module.Sender(SimpleNamespace(
            suppress_answer_ms=0, log_dir=self.directory.name,
            label="bridge-test", bridge_port=self.server.getsockname()[1],
        ))
        self.messages = []
        self.sender.channel = SimpleNamespace(
            emit=lambda signal, message: self.messages.append(message)
        )
        self.sender.channel_open = True

    def tearDown(self):
        self.sender.stop_bridge()
        for peer in self.peers:
            peer.close()
        for worker in self.sender._bridge_threads:
            worker.join(timeout=1)
        self.sender._wslog.close()
        self.server.close()
        self.dispatch.stop()
        self.directory.cleanup()

    def connect(self):
        self.sender.start_bridge()
        peer, _ = self.server.accept()
        peer.settimeout(1)
        self.peers.append(peer)
        return peer

    def drain(self):
        while not self.callbacks.empty():
            fn, args = self.callbacks.get_nowait()
            fn(*args)

    def test_stop_unblocks_reader_and_reconnect_owns_one_socket(self):
        first = self.connect()
        old_workers = list(self.sender._bridge_threads)
        self.sender.stop_bridge()
        # Reconnect immediately, while the old reader/writer may still be alive.
        second = self.connect()
        for worker in old_workers:
            worker.join(timeout=1)
        self.assertFalse(any(worker.is_alive() for worker in old_workers))
        self.assertEqual(first.recv(1), b"", "detach must close Unity's socket")
        self.sender._bridge_queue.put("new-attachment")
        self.assertEqual(second.recv(128), b"new-attachment\n")
        self.server.settimeout(0.05)
        with self.assertRaises(socket.timeout):
            self.server.accept()
        self.drain()
        self.assertTrue(self.sender.channel_open, "old reader cannot tear down new peer")

    def test_retired_reader_cannot_deliver_queued_state_to_new_peer(self):
        first = self.connect()
        first.sendall(b'{"type":"state","epoch":"old"}\n')
        callback = self.callbacks.get(timeout=1)
        self.sender.stop_bridge()
        self.connect()
        callback[0](*callback[1])
        self.assertEqual(self.messages, [], "discard late GLib callbacks from old bridge")

    def test_retired_disconnect_cannot_teardown_new_peer(self):
        first = self.connect()
        first.shutdown(socket.SHUT_RDWR)
        first.close()
        callback = self.callbacks.get(timeout=1)
        self.sender.stop_bridge()
        self.connect()
        callback[0](*callback[1])
        self.assertTrue(self.sender.channel_open)

    def test_hello_waits_for_unity_during_cold_start(self):
        connect = socket.create_connection
        allow_connect = threading.Event()
        def delayed_connect(*args, **kwargs):
            allow_connect.wait(timeout=1)
            return connect(*args, **kwargs)
        try:
            with patch.object(sender_module.socket, "create_connection", side_effect=delayed_connect):
                self.sender.start_bridge()
                self.sender._on_channel_string(None, '{"type":"hello"}')
                deadline = time.monotonic() + 1
                while not self.sender._bridge_queue.empty() and time.monotonic() < deadline:
                    time.sleep(0.005)
                allow_connect.set()
                peer, _ = self.server.accept(); peer.settimeout(0.2); self.peers.append(peer)
                self.assertEqual(peer.recv(128), b'{"type":"hello"}\n')
        finally:
            allow_connect.set()

    def test_capture_marker_maps_exact_running_time_to_rtp_timestamp(self):
        gst = sender_module.Gst
        raw_segment = gst.Segment(); raw_segment.init(gst.Format.TIME)
        encoded_segment = gst.Segment(); encoded_segment.init(gst.Format.TIME)
        encoded_segment.start = 3_600_000_000_000_000 - 13_000_000
        raw_pad = SimpleNamespace(
            get_current_caps=lambda: gst.Caps.from_string('video/x-raw,format=BGRx,width=1920,height=1080'),
            get_sticky_event=lambda *_: gst.Event.new_segment(raw_segment),
        )
        rtp_pad = SimpleNamespace(get_sticky_event=lambda *_: gst.Event.new_segment(encoded_segment))
        stop = self.sender._bridge_stop
        for index, frame_id in enumerate((65535, 0)):
            capture = gst.Buffer.new_allocate(None, 1920 * 4 * 16, None)
            capture.pts = 13_000_000 + index * 16_666_667
            bits = (0xd3 << 24) | (frame_id << 8) | (((frame_id >> 8) ^ frame_id ^ 0x5a) & 255)
            row = b''.join(bytes([255 if bits & (1 << (31 - i)) else 0] * 3 + [255]) * 8 for i in range(32))
            capture.fill(1920 * 4 * 8, row)
            self.sender._capture_frame_marker(raw_pad, SimpleNamespace(get_buffer=lambda: capture), stop)
            timestamp = (0xfffffff0 + index * 1500) & 0xffffffff
            packet = gst.Buffer.new_allocate(None, 12, None)
            packet.pts = encoded_segment.start + capture.pts
            packet.fill(0, b'\x80\x7b\x00\x01' + timestamp.to_bytes(4, 'big') + b'\x00' * 4)
            info = SimpleNamespace(type=gst.PadProbeType.BUFFER, get_buffer=lambda: packet)
            self.sender._map_video_frame(rtp_pad, info, stop)
            self.sender._map_video_frame(rtp_pad, info, stop)  # later packets of the same access unit
            self.drain()
            self.assertEqual(self.messages[-1],
                '{"type": "video_frame", "rtp_timestamp": %d, "frame_id": %d}' % (timestamp, frame_id))
        self.assertEqual(len(self.messages), 2, 'one mapping per encoded video frame, including wraparound')


if __name__ == "__main__":
    unittest.main()
