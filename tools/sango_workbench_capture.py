import json
import signal
import socket
import subprocess
import time
import argparse
import hashlib
from pathlib import Path
import zmq

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description='Local CPU YOLO + native onboard workbench acceptance and source capture')
parser.add_argument('--out', type=Path, default=root / 'output/aeolus-workbench-20261001')
parser.add_argument('--record-video', action='store_true', help='Record native screen frames only after FPS measurements')
parser.add_argument('--fixed-camera', action='store_true', help='Disable truth-assisted camera aiming in onboard acceptance')
args = parser.parse_args()
base = args.out.resolve()
base.mkdir(parents=True, exist_ok=True)
python = root / '.venv-detector/bin/python'
for port in (5556, 5557):
    with socket.socket() as check:
        check.bind(('127.0.0.1', port))
context = zmq.Context()
sub = context.socket(zmq.SUB)
sub.setsockopt(zmq.SUBSCRIBE, b'sango.frame')
sub.setsockopt(zmq.LINGER, 0)
sub.connect('tcp://127.0.0.1:5556')
det_sub = context.socket(zmq.SUB)
det_sub.setsockopt(zmq.SUBSCRIBE, b'sango.detection')
det_sub.setsockopt(zmq.LINGER, 0)
det_sub.connect('tcp://127.0.0.1:5557')
poller = zmq.Poller(); poller.register(sub, zmq.POLLIN); poller.register(det_sub, zmq.POLLIN)
frames = base / 'sensor-frames'; frames.mkdir(exist_ok=True)
player = None
with (base / 'detector.log').open('w') as log, (base / 'sensor-frames.jsonl').open('w') as frame_log, (base / 'results.jsonl').open('w') as results:
    detector = subprocess.Popen([str(python), '-u', 'tools/sango_detector_service.py', '--device', 'cpu', '--log-every', '30'], cwd=root, stdout=log, stderr=subprocess.STDOUT)
    try:
        time.sleep(3)
        if detector.poll() is not None: raise RuntimeError('Detector failed to start')
        player = subprocess.Popen([str(root / 'sango/Builds/sango.app/Contents/MacOS/sango'), '--sango-publisher', '--sango-workbench-verify', str(base / 'native'), *(['--sango-workbench-video'] if args.record_video else []), *(['--sango-workbench-fixed-camera'] if args.fixed_camera else []), '-screen-width', '2560', '-screen-height', '1440', '-screen-fullscreen', '0', '-logFile', str(base / 'player.log')], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 360
        count = 0
        while player.poll() is None:
            if time.monotonic() > deadline: raise TimeoutError('Native verification timed out')
            ready = dict(poller.poll(100))
            if sub in ready:
                parts = sub.recv_multipart(); meta = json.loads(parts[1])
                file = f'{count:05d}.jpg'; (frames / file).write_bytes(parts[2])
                frame_log.write(json.dumps({'file': file, **meta}) + '\n')
                count += 1
                if count % 300 == 0: frame_log.flush(); results.flush(); print(f'captured {count} clean sensor frames', flush=True)
            if det_sub in ready:
                parts = det_sub.recv_multipart(); results.write(parts[1].decode() + '\n')
        report = json.loads((base / 'native/report.json').read_text())
        identity = {'model': str(root / 'models/yolov8n.pt'), 'sha256': hashlib.sha256((root / 'models/yolov8n.pt').read_bytes()).hexdigest(), 'device': 'cpu', 'frame_metadata': 'sensor-frames.jsonl', 'actual_results': 'results.jsonl', 'scene': 'native/scene.json'}
        (base / 'model-and-capture.json').write_text(json.dumps(identity, indent=2) + '\n')
        print(json.dumps({'exit': player.returncode, 'frames': count, 'passed': report['passed'], 'failures': report['failures'], 'windows': report['windows']}), flush=True)
    finally:
        if player is not None and player.poll() is None: player.terminate(); player.wait(timeout=15)
        if detector.poll() is None: detector.send_signal(signal.SIGINT); detector.wait(timeout=15)
        sub.close(); det_sub.close(); context.term()
