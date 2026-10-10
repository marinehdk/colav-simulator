#!/usr/bin/env python3
"""Linux renderer process group; isolated from every existing A4000 service."""

# ruff: noqa: D103

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "renderer-pids.json"
LOG = ROOT / "logs"
LOG.mkdir(exist_ok=True)


def alive(pid: int) -> bool:
    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes()
        return str(ROOT).encode() in cmd or b"Xvfb" in cmd and b":93" in cmd
    except OSError:
        return False


def status() -> dict[str, int]:
    pids = json.loads(STATE.read_text()) if STATE.exists() else {}
    return {name: pid for name, pid in pids.items() if alive(pid)}


def stop():
    pids = status()
    for name in ("player", "signaling", "display"):
        pid = pids.get(name)
        if pid:
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 4
    while any(alive(p) for p in pids.values()) and time.monotonic() < deadline:
        time.sleep(0.1)
    for pid in pids.values():
        if alive(pid):
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    STATE.unlink(missing_ok=True)


def spawn(name: str, args: list[str], env: dict[str, str] | None = None, cwd: Path | None = None) -> int:
    with (LOG / f"{name}.log").open("ab") as output:
        return subprocess.Popen(
            args, env=env, cwd=cwd or ROOT, stdout=output, stderr=subprocess.STDOUT, start_new_session=True
        ).pid


def start() -> dict[str, int]:
    pids = status()
    if set(pids) == {"display", "signaling", "player"}:
        return pids
    stop()
    pids = {}
    try:
        pids["display"] = spawn("display", ["Xvfb", ":93", "-screen", "0", "2560x1440x24", "-nolisten", "tcp"])
        pids["signaling"] = spawn(
            "signaling",
            [str(ROOT / "node/bin/node"), str(ROOT / "signaling/build/index.js"), "-p", "8080"],
            cwd=ROOT / "signaling",
        )
        STATE.write_text(json.dumps(pids))
        time.sleep(0.5)
        # Bind the system C++ runtime before Unity/WebRTC to avoid the NVENC
        # initialization symbol collision observed on the deployed Linux player.
        env = dict(os.environ, DISPLAY=":93", LD_PRELOAD="/lib/x86_64-linux-gnu/libstdc++.so.6")
        pids["player"] = spawn(
            "player",
            [
                str(ROOT / "player/sango.x86_64"),
                "--sango-twin-bridge",
                "-force-vulkan",
                "-force-device-index",
                "0",
                "-screen-fullscreen",
                "0",
                "-screen-width",
                "640",
                "-screen-height",
                "360",
                "-logFile",
                str(LOG / "unity-player.log"),
            ],
            env=env,
        )
        STATE.write_text(json.dumps(pids))
        return pids
    except Exception:
        STATE.write_text(json.dumps(pids))
        stop()
        raise


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "start":
        result = start()
    elif action == "stop":
        stop()
        result = {}
    elif action == "status":
        result = status()
    else:
        raise ValueError("unknown action")
    print(json.dumps(result))
