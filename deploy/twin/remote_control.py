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
    command = shlex.join(["python3", CFG["remote_root"] + "/renderer_control.py", action])
    return call([*BASE, "-S", str(SOCKET), HOST, command])


def start():
    check = call([*BASE, "-S", str(SOCKET), "-O", "check", HOST], required=False)
    if check.returncode:
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
                "-R",
                "127.0.0.1:18010:127.0.0.1:8010",
                "-L",
                "127.0.0.1:8080:127.0.0.1:8080",
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
