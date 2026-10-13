#!/usr/bin/env python3
"""M1 验收 3:webrtcbin PLAYING 探针(gstreamer1.0-nice 在位的运行时证明)。

构建最小编码发送支线接入 webrtcbin,置 PLAYING 并创建 data channel,
监听总线 >=6s:无 "missing a plug-in" / "libnice" 类错误 => 通过。
背景:无 gstreamer1.0-nice 时 gst-inspect webrtcbin 照样通过(验收盲区),
webrtcbin 一投用即总线报错(gstwebrtcbin.c:154;DESIGN 附录 C1 复审实证)。

用法:docker exec gst-base python3 /gst/probe/webrtcbin_probe.py
退出码:0=通过;1=检出缺件错误 / 未达 PLAYING。
阴性对照(证探针判别力):--rm 容器内 mv 走 libgstnice.so 后本探针必须报 FAIL。
"""
import re
import sys

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib  # noqa: E402

DURATION_S = 6
BAD = re.compile(r"missing a plug-in|libnice", re.I)

PIPELINE = (
    "videotestsrc is-live=true ! video/x-raw,width=320,height=180,framerate=30/1 ! "
    "videoconvert ! "
    "nvautogpuh264enc cuda-device-id=1 preset=p4 tune=ultra-low-latency rate-control=cbr b-frames=0 "
    "zero-reorder-delay=true rc-lookahead=0 gop-size=60 repeat-sequence-header=true qos=true ! "
    "h264parse ! rtph264pay config-interval=-1 ! "
    "application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000,"
    "packetization-mode=1,profile-level-id=42e033 ! webrtcbin name=wb"
)


def main() -> int:
    Gst.init(None)
    pipeline = Gst.parse_launch(PIPELINE)
    wb = pipeline.get_by_name("wb")
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    msgs = []

    def on_msg(_bus, msg):
        texts = []
        if msg.type == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            texts.append(f"ERROR {err.message} debug={dbg}")
        elif msg.type == Gst.MessageType.WARNING:
            err, dbg = msg.parse_warning()
            texts.append(f"WARNING {err.message} debug={dbg}")
        for t in texts:
            msgs.append(t)
            print("[bus]", t, flush=True)

    bus.connect("message", on_msg)

    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        print("PROBE_FAIL: set_state(PLAYING) returned FAILURE")
        return 1
    print(f"[probe] set_state -> {ret.value_nick}")

    # data channel 触发 application transport 创建,与视频支线共同构成"投用"
    ch = None
    for args in (("probe", None), ("probe",)):
        try:
            ch = wb.emit("create-data-channel", *args)
            print(f"[probe] create-data-channel{args} -> {ch}")
            break
        except Exception as e:  # noqa: BLE001
            print(f"[probe] create-data-channel{args} exception: {e}")

    loop = GLib.MainLoop()
    GLib.timeout_add_seconds(DURATION_S, loop.quit)
    loop.run()

    _, state, _ = pipeline.get_state(0)
    print(f"[probe] final state: {state.value_nick}")
    bus.remove_signal_watch()
    pipeline.set_state(Gst.State.NULL)

    bad = [m for m in msgs if BAD.search(m)]
    # 预期内噪音:无远端时 webrtcbin sink 无从协商 caps, videotestsrc 报
    # "streaming stopped, reason not-negotiated" —— 与 nice 缺件无关, 不计入 FAIL。
    for m in msgs:
        if "not-negotiated" in m:
            print("[probe] expected without remote peer: not-negotiated on video branch")
    if bad:
        print(f"PROBE_FAIL: {len(bad)} bus message(s) match missing-plugin/libnice")
        return 1
    if state != Gst.State.PLAYING:
        print("PROBE_FAIL: pipeline did not stay PLAYING")
        return 1
    print(
        f"PROBE_OK: PLAYING for {DURATION_S}s, {len(msgs)} error/warning bus msgs, "
        f"data-channel={'created' if ch else 'n/a'}, no missing-plugin/libnice"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
