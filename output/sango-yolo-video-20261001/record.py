import json
import signal
import socket
import subprocess
import time
from pathlib import Path

import zmq

base = Path(__file__).resolve().parent
root = base.parents[1]
python = root / '.venv-detector/bin/python'
frames = base / 'frames'
frames.mkdir(exist_ok=True)
for port in (5556, 5557):
    with socket.socket() as check:
        check.bind(('127.0.0.1', port))

context = zmq.Context()
frame_sub = context.socket(zmq.SUB)
frame_sub.setsockopt(zmq.SUBSCRIBE, b'sango.frame')
frame_sub.setsockopt(zmq.LINGER, 0)
frame_sub.connect('tcp://127.0.0.1:5556')
result_sub = context.socket(zmq.SUB)
result_sub.setsockopt(zmq.SUBSCRIBE, b'sango.detection')
result_sub.setsockopt(zmq.LINGER, 0)
result_sub.connect('tcp://127.0.0.1:5557')
poller = zmq.Poller()
poller.register(frame_sub, zmq.POLLIN)
poller.register(result_sub, zmq.POLLIN)
player = None
frame_count = result_count = 0
with (base / 'detector.log').open('w') as log, (base / 'frames.jsonl').open('w') as frame_log, (base / 'results.jsonl').open('w') as result_log:
    detector = subprocess.Popen([str(python), '-u', 'tools/sango_detector_service.py', '--device', 'cpu', '--log-every', '30'], cwd=root, stdout=log, stderr=subprocess.STDOUT)
    try:
        time.sleep(3)
        if detector.poll() is not None:
            raise RuntimeError('CPU detector failed to start')
        player = subprocess.Popen([str(root / 'sango/Builds/sango.app/Contents/MacOS/sango'), '--sango-publisher', '--sango-verify', str(base / 'verification'), '-screen-width', '2560', '-screen-height', '1440', '-screen-fullscreen', '0', '-logFile', str(base / 'player.log')], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 240
        while player.poll() is None:
            if time.monotonic() > deadline:
                raise TimeoutError('recording player did not finish')
            ready = dict(poller.poll(100))
            if frame_sub in ready:
                parts = frame_sub.recv_multipart()
                if len(parts) != 3 or parts[0] != b'sango.frame':
                    raise ValueError('unexpected frame multipart')
                meta = json.loads(parts[1])
                name = f'{frame_count:05d}.jpg'
                (frames / name).write_bytes(parts[2])
                frame_log.write(json.dumps({'file': name, **meta}) + '\n')
                frame_count += 1
                if frame_count % 300 == 0:
                    print(f'captured {frame_count} full-size frames', flush=True)
            if result_sub in ready:
                parts = result_sub.recv_multipart()
                if len(parts) == 2:
                    result_log.write(parts[1].decode() + '\n')
                    result_count += 1
        print(f'player exit={player.returncode}; frames={frame_count}; YOLO results={result_count}', flush=True)
        if player.returncode != 0 or frame_count == 0:
            raise RuntimeError('native capture failed')
    finally:
        if player is not None and player.poll() is None:
            player.terminate()
            player.wait(timeout=15)
        if detector.poll() is None:
            detector.send_signal(signal.SIGINT)
            detector.wait(timeout=15)
        frame_sub.close()
        result_sub.close()
        context.term()
