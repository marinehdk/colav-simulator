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

    @staticmethod
    def marker_row_bytes(frame_id):
        bits = (0xd3 << 24) | (frame_id << 8) | (((frame_id >> 8) ^ frame_id ^ 0x5a) & 255)
        return b''.join(bytes([255 if bits & (1 << (31 - i)) else 0] * 3 + [255]) * 8 for i in range(32))

    def fill_marker_rows(self, buffer, width, rows, frame_id):
        row = self.marker_row_bytes(frame_id)
        for r in rows:
            buffer.fill(width * 4 * r, row)

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
            self.fill_marker_rows(capture, 1920, sender_module.Sender.MARKER_SAMPLE_ROWS, frame_id)
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

    def test_capture_tap_marker_stamps_frame_id_by_pts(self):
        """检测分流帧标识:缩放前探针 pts→frame_id,取用精确命中 + ±40ms 近邻兜底
        (720p 分流帧像素 marker 不可解码,frame_id 只能由元数据携带——20261020)。"""
        gst = sender_module.Gst
        pad = SimpleNamespace(
            get_current_caps=lambda: gst.Caps.from_string('video/x-raw,format=BGRx,width=2560,height=1440'))
        pts_a, pts_b = 5_000_000_000, 5_016_666_667
        for pts, frame_id in ((pts_a, 1234), (pts_b, 65535)):
            capture = gst.Buffer.new_allocate(None, 2560 * 4 * 16, None)
            capture.pts = pts
            self.fill_marker_rows(capture, 2560, sender_module.Sender.MARKER_SAMPLE_ROWS, frame_id)
            self.sender._capture_tap_marker(pad, SimpleNamespace(get_buffer=lambda: capture))
        self.assertEqual(self.sender._tap_frame_id_for(pts_b), 65535, '精确 pts 命中')
        self.assertEqual(self.sender._tap_frame_id_for(pts_a + 3_000_000), 1234,
                         '±40ms 近邻兜底(jpegenc pts 微差)')
        self.assertIsNone(self.sender._tap_frame_id_for(9_999_999_999), '超窗未命中返 None')
        self.assertIsNone(self.sender._tap_frame_id_for(gst.CLOCK_TIME_NONE), '无 pts 返 None')

    def test_decode_marker_survives_row_smear(self):
        """三期回归锁(20261020 empty 89% 根因):快速转视角时 TAA 幽影/亮部泛光
        逐行污染 marker 条带——部分采样行落歧义窗时,其余行的校验和票选必须救回
        frame_id;全行污染才允许失败(近邻兜底/stamp 由调用方接手)。"""
        gst = sender_module.Gst
        pad = SimpleNamespace(
            get_current_caps=lambda: gst.Caps.from_string('video/x-raw,format=BGRx,width=2560,height=1440'))
        rows = sender_module.Sender.MARKER_SAMPLE_ROWS
        smear = bytes([128, 128, 128, 255]) * 256  # 歧义窗灰:该行必须弃权
        capture = gst.Buffer.new_allocate(None, 2560 * 4 * 16, None)
        self.fill_marker_rows(capture, 2560, rows, 4242)
        for r in rows[:3]:  # 污染一半采样行
            capture.fill(2560 * 4 * r, smear)
        self.assertEqual(self.sender._decode_marker_pad(pad, SimpleNamespace(get_buffer=lambda: capture)), 4242,
                         '部分行拖影:干净行多数票救回')
        self.assertGreater(self.sender._marker_rows_recovered, 0, '救回计数入账(30s 诊断账本)')
        self.assertEqual(self.sender._marker_decode_fails, 0)
        all_smeared = gst.Buffer.new_allocate(None, 2560 * 4 * 16, None)
        for r in rows:
            all_smeared.fill(2560 * 4 * r, smear)
        self.assertIsNone(self.sender._decode_marker_pad(pad, SimpleNamespace(get_buffer=lambda: all_smeared)),
                          '全行拖影:fail-closed 返 None')
        self.assertEqual(self.sender._marker_decode_fails, 1)

    def test_decode_marker_survives_bloom(self):
        """四期回归锁(20261021 泄漏帧实锤):本船白色上层建筑泛光把黑格均匀抬进
        歧义窗(黑~150/白~210,固定窗口解码 all_rows_failed 23%);行内自适应阈值
        按相对序照常解出,魔数+校验和门控保持 fail-closed。"""
        gst = sender_module.Gst
        pad = SimpleNamespace(
            get_current_caps=lambda: gst.Caps.from_string('video/x-raw,format=BGRx,width=2560,height=1440'))
        bits = (0xd3 << 24) | (4242 << 8) | (((4242 >> 8) ^ 4242 ^ 0x5a) & 255)
        bloomed = b''.join(bytes([210 if bits & (1 << (31 - i)) else 150] * 3 + [255]) * 8 for i in range(32))
        capture = gst.Buffer.new_allocate(None, 2560 * 4 * 16, None)
        for r in sender_module.Sender.MARKER_SAMPLE_ROWS:
            capture.fill(2560 * 4 * r, bloomed)
        self.assertEqual(self.sender._decode_marker_pad(pad, SimpleNamespace(get_buffer=lambda: capture)), 4242,
                         '均匀泛光抬升黑格:自适应阈值按相对序解出')

    def test_decode_marker_majority_beats_single_adversarial_row(self):
        """单行碰巧通过魔数+校验和的对抗位串不得劫持票选:多数行赢。"""
        gst = sender_module.Gst
        pad = SimpleNamespace(
            get_current_caps=lambda: gst.Caps.from_string('video/x-raw,format=BGRx,width=2560,height=1440'))
        rows = sender_module.Sender.MARKER_SAMPLE_ROWS
        capture = gst.Buffer.new_allocate(None, 2560 * 4 * 16, None)
        self.fill_marker_rows(capture, 2560, rows, 1234)
        capture.fill(2560 * 4 * rows[-1], self.marker_row_bytes(5678))  # 最后一行改投合法异值
        self.assertEqual(self.sender._decode_marker_pad(pad, SimpleNamespace(get_buffer=lambda: capture)), 1234,
                         '5:1 票型多数赢')


if __name__ == "__main__":
    unittest.main()
