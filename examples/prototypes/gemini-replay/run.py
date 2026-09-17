"""One-command launcher for the disposable, real Gemini/Unity replay."""
from pathlib import Path
import json
import os
import plistlib
import subprocess
import sys
import urllib.request

root = Path(__file__).resolve().parent
python = root / ".build/venv/bin/python"
outputs = root / "outputs"
outputs.mkdir(exist_ok=True)
env = {**os.environ, "COLAV_GEMINI_OUTPUT": str(outputs)}
try:
    running = json.load(urllib.request.urlopen("http://127.0.0.1:8127/status", timeout=1))
    expected = json.loads((root / "data/replay.json").read_text())["run_id"]
    if running.get("run_id") != expected: raise SystemExit("Port 8127 belongs to another run; stop that prototype first.")
except OSError:
    log = open(outputs / "python-replay.log", "a")
    subprocess.Popen([str(python), str(root / "client/replay.py")], env=env,
                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
app = outputs / "Gemini-Colav-Replay.app"
if app.exists():
    with open(app / "Contents/Info.plist", "rb") as stream:
        executable = plistlib.load(stream)["CFBundleExecutable"]
    binary = str(app / "Contents/MacOS" / executable)
    pid_file = outputs / "player.pid"
    alive = False
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        command = subprocess.run(["ps", "-p", pid, "-o", "comm="], capture_output=True, text=True)
        alive = command.returncode == 0 and command.stdout.strip() == binary
    if not alive:
        player_log = open(outputs / "player-stdout.log", "a")
        process = subprocess.Popen([binary], env=env, start_new_session=True,
                                   stdin=subprocess.DEVNULL, stdout=player_log, stderr=subprocess.STDOUT)
        pid_file.write_text(str(process.pid))
else:
    editor = Path("/Applications/Unity/Hub/Editor/2019.4.20f1/Unity.app/Contents/MacOS/Unity")
    if not editor.exists(): raise SystemExit("Unity 2019.4.20f1 not installed at " + str(editor))
    subprocess.Popen([str(editor), "-projectPath", str(root / "unity"),
                      "-executeMethod", "ColavPrototypeEditor.Play", "-logFile", str(outputs / "Unity.log")],
                     env=env, start_new_session=True)
subprocess.run(["open", "http://127.0.0.1:8127"], check=True)
print("Unity renders the scene; http://127.0.0.1:8127 controls the recorded playback.")
