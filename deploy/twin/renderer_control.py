#!/usr/bin/env python3
"""Linux renderer process group; isolated from every existing A4000 service."""

# ruff: noqa: D103

import json
import os
import signal
import socket
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


def status_full() -> dict[str, int | str]:
    """Status view for twinctl (M4): STATE pids + docker inspect dual-track.

    任意路由都显示 gst 容器/发送器态(DESIGN §5.3;A6:legacy 终态也要能看见容器 stopped)。
    """
    out: dict[str, int | str] = dict(status())
    out["gst"] = gst_container_state()
    out["gst_sender"] = "up" if _gst_sender_up() else "down"
    return out


def _route() -> str:
    # M3 gst 模式门控(DESIGN §2 M3/§5.3):TWIN_VIDEO_ROUTE=gst-xvfb 时窗口 2560x1440。
    # 默认(无 env)= legacy-urs,行为与旧版逐字节等价。M4 将由 remote-runtime.json 驱动。
    return os.environ.get("TWIN_VIDEO_ROUTE", "legacy-urs")


def _player_window() -> tuple[str, str]:
    override = os.environ.get("TWIN_PLAYER_WINDOW", "").lower()
    if override:  # 实验档显式覆盖,如 1080p 档 1920x1080
        w, h = override.split("x")
        return w, h
    if _route() == "gst-xvfb":
        return "2560", "1440"
    return "640", "360"


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ── M4:gst 容器组(DESIGN §5.3/§5.1;仅 gst-xvfb 路由拉起,legacy 分支 start 不触碰)──
GST_CONTAINER = os.environ.get("TWIN_GST_CONTAINER", "gst-base")  # M1 常驻底座容器
GST_SENDER = "/gst/sender/sender.py"  # run.sh volume:~/gst-spike/gst → /gst(ro)
GST_BITRATE = os.environ.get("TWIN_GST_BITRATE", "20000")  # kbps;M3 1440p 达标档(1080p 手动实验 16000)
GST_WARMUP = (
    "gst-launch-1.0 -e videotestsrc num-buffers=300 "
    "! video/x-raw,width=640,height=360,format=NV12,framerate=30/1 "
    "! cudaupload ! nvautogpuh264enc cuda-device-id=1 ! fakesink"
)  # GPU1 NVENC 冷启动预热(M1 warmup.sh/T4 坑)


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False)


def gst_container_state() -> str:
    """Container state via docker inspect: running|exited|missing."""
    r = _docker("inspect", "-f", "{{.State.Status}}", GST_CONTAINER)
    return r.stdout.strip() or "missing" if r.returncode == 0 else "missing"


def _gst_sender_up() -> bool:
    return _docker("exec", GST_CONTAINER, "pgrep", "-f", "sender.py").returncode == 0


def _start_gst_group() -> str:
    """拉起 gst 组(容器+sender),player 之后调用;幂等:容器在跑免预热,sender 在跑跳过."""
    state = gst_container_state()
    if state == "missing":
        raise RuntimeError(f"docker container {GST_CONTAINER} missing; build per deploy/twin/gst/run.sh")
    if state != "running":
        _docker("start", GST_CONTAINER)
        _docker("exec", GST_CONTAINER, "bash", "-c", GST_WARMUP)  # 阻塞 ~10s,仅冷启动
    if _gst_sender_up():
        return "sender-already-up"
    label = "gst-" + time.strftime("%m%d%H%M")
    w, h = _player_window()  # 与 player 窗口同源(ximagesrc 抓 Xvfb 屏,窗口=采集区)
    _docker(
        "exec", "-d", GST_CONTAINER, "sh", "-c",
        f"mkdir -p /out/spike && exec python3 {GST_SENDER} --label {label} --source x11 "
        f"--width {w} --height {h} --fps 30 --bitrate {GST_BITRATE} --gop-size 30 "
        f"> /out/spike/sender-{label}.log 2>&1",
    )  # M3 达标参数:gop=30(丢包突发恢复上界 1s,笔记 03 §2)
    time.sleep(2)
    if not _gst_sender_up():
        raise RuntimeError(f"sender died on startup; see ~/gst-spike/bench/spike/sender-{label}.log")
    return label


def _stop_gst_group() -> None:
    """停 gst 组:sender(优雅 teardown)→ 容器 → webapp 8081(含 M2 手工实例).

    任意路由的 stop 都执行,保证 twinctl stop/restart 后无残留组(legacy 定义=无 gst 容器)。
    """
    _docker("exec", GST_CONTAINER, "pkill", "-f", "sender.py")
    _docker("stop", GST_CONTAINER)  # 幂等:已停 no-op;missing 报错忽略
    subprocess.run(["pkill", "-f", "signaling/build/index.js -p 8081"], capture_output=True, check=False)


def _spawn_player() -> int:
    # 证书 env(2026-10-11 热修回归项):Unity 内置 CA 不认 Cesium 新根(Starfield G2),
    # 不指系统 bundle 时 ion 请求挂 → terrain=0 且不自愈;跨 session 缓存会掩盖该失败。
    env = dict(
        os.environ,
        DISPLAY=":93",
        LD_PRELOAD="/lib/x86_64-linux-gnu/libstdc++.so.6",
        SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt",
        CURL_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt",
        REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt",
    )
    w, h = _player_window()
    return spawn(
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
            w,
            "-screen-height",
            h,
            "-logFile",
            str(LOG / "unity-player.log"),
        ],
        env=env,
    )


def restart_player() -> dict[str, int]:
    """M3:只重启 player(窗口档切换);display/signaling 现役不动(实施守则 1)."""
    pids = status()
    if not {"display", "signaling"} <= set(pids):
        raise RuntimeError("display/signaling not running; use start instead")
    old = pids.get("player")
    if old:
        try:
            os.killpg(old, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 8
        while alive(old) and time.monotonic() < deadline:
            time.sleep(0.1)
        if alive(old):
            try:
                os.killpg(old, signal.SIGKILL)
            except ProcessLookupError:
                pass
    pids["player"] = _spawn_player()
    STATE.write_text(json.dumps(pids))
    return pids


def stop():
    _stop_gst_group()  # 反向顺序第一步(M4):gst 组先于 player 停
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
    route = _route()
    expected = {"display", "signaling", "player"} | ({"signaling-8081"} if route == "gst-xvfb" else set())
    pids = status()
    if set(pids) == expected:
        if route == "gst-xvfb":
            _start_gst_group()  # 幂等补齐:容器被停过/ sender 死过则拉回
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
        if route == "gst-xvfb" and not _port_open(8081):
            # M3 gst 模式:第二 webapp 实例 8081(浏览器+gst sender 隔离信令室,
            # DESIGN §5.3;幂等守卫:已在监听(如手工实例)则跳过且不进 STATE,
            # 下轮 start 幂等检查不匹配 → 全量重启时会被 _stop_gst_group 收编)
            pids["signaling-8081"] = spawn(
                "signaling-8081",
                [str(ROOT / "node/bin/node"), str(ROOT / "signaling/build/index.js"), "-p", "8081"],
                cwd=ROOT / "signaling",
            )
        STATE.write_text(json.dumps(pids))
        time.sleep(0.5)
        # Bind the system C++ runtime before Unity/WebRTC to avoid the NVENC
        # initialization symbol collision observed on the deployed Linux player.
        pids["player"] = _spawn_player()
        STATE.write_text(json.dumps(pids))
        if route == "gst-xvfb":
            _start_gst_group()  # 启停顺序末位:display→signaling→player→gst(DESIGN §5.3)
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
        result = status_full()
    elif action == "restart-player":
        result = restart_player()
    else:
        raise ValueError("unknown action")
    print(json.dumps(result))
