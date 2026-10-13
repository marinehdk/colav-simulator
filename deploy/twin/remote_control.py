#!/usr/bin/env python3
"""Own only the DT SSH tunnel and the isolated remote renderer service."""

# ruff: noqa: D103

import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / "deploy/twin/remote-runtime.json").read_text())
ROUTE = CFG.get("video_route", "legacy-urs")  # M3 gst 模式门控(DESIGN §5.3);默认 legacy 零行为差
SOCKET = ROOT / "deploy/twin/logs/renderer-ssh.sock"
SOCKET.parent.mkdir(exist_ok=True)
HOST = CFG["host"]
BASE = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]


def call(args: list[str], *, required: bool = True) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
    if required and r.returncode:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return r


def remote(action: str) -> subprocess.CompletedProcess[str]:
    cmd = ["python3", CFG["remote_root"] + "/renderer_control.py", action]
    env_prefix = []
    if ROUTE != "legacy-urs":
        env_prefix.append(f"TWIN_VIDEO_ROUTE={ROUTE}")  # env 前缀经 ssh 远端 shell 生效
        if CFG.get("player_window"):
            # M5:gst 档窗口固化(免每次 env 直连)。legacy 不透传——保 640×360 逐字节等价。
            env_prefix.append(f"TWIN_PLAYER_WINDOW={CFG['player_window']}")
    cmd = env_prefix + cmd
    command = shlex.join(cmd)
    return call([*BASE, "-S", str(SOCKET), HOST, command])


def start():
    check = call([*BASE, "-S", str(SOCKET), "-O", "check", HOST], required=False)
    if check.returncode:
        if ROUTE == "gst-xvfb":
            # M5 变体 B 重映射(DESIGN §5.3):浏览器信令 URL 不变(本地 8080,healthMonitor
            # 探测与视口构造期固化均指向它),但落点改投 gst 信令室 8081——Unity 仍挂远程
            # 8080 闲置,永不与 sender 同室。8081 直连保留作 spike/诊断入口。
            forwards = [
                "-R", "127.0.0.1:18010:127.0.0.1:8010",
                "-L", "127.0.0.1:8080:127.0.0.1:8081",
                "-L", "127.0.0.1:8081:127.0.0.1:8081",
            ]
        else:
            forwards = [
                "-R", "127.0.0.1:18010:127.0.0.1:8010",
                "-L", "127.0.0.1:8080:127.0.0.1:8080",
            ]
        call(
            [
                *BASE,
                "-M",
                "-S",
                str(SOCKET),
                "-fNT",
                "-o",
                "ExitOnForwardFailure=yes",
                "-o",
                "ServerAliveInterval=15",
                "-o",
                "ServerAliveCountMax=3",
                *forwards,
                HOST,
            ]
        )
    print(remote("start").stdout)


def stop():
    try:
        print(remote("stop").stdout)
    finally:
        call([*BASE, "-S", str(SOCKET), "-O", "exit", HOST], required=False)


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "start":
        start()
    elif action == "stop":
        stop()
    elif action == "restart":
        stop()
        start()
    elif action == "status":
        print(remote("status").stdout)
    else:
        raise ValueError("unknown renderer action")


if __name__ == "__main__":
    main()
