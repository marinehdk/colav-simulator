#!/usr/bin/env python3
"""Xvfb 帧缓冲更新节律探针 — 拉扯感(content-level judder)取证。

背景:Unity(targetFrameRate=60,vSync=0)自由时钟渲染进 Xvfb,sender ximagesrc
以独立 Gst 时钟旁路采帧 → 采集时刻 vs 渲染完成时刻存在竞态,可能输出
「同帧重复/跨帧跳步」的内容序列 — FPS 指标(包节拍均匀)完全看不见,
只有逐帧内容差分能暴露。

用法(容器内): python3 fb_pacer.py --display :93 --width 1920 --height 1080 \
    --rate 120 --seconds 30
输出: /out/fb-pacer-<rate>.jsonl 每行:
  {"t": pts_ms, "wc": wall_ms, "h": md5_10, "dup": 0/1,
   "md": meanAbsDiff, "fchg": changedFrac}
  dup=1 与上一采样内容完全相同(md5 相等);md/fchg 仅在内容变化时计算。
"""
import argparse
import hashlib
import json
import sys
import time

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--display", default=":93")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--rate", type=int, default=120)
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--stride", type=int, default=32, help="采样像素间距(px)")
    a = ap.parse_args()

    Gst.init(None)
    src = Gst.ElementFactory.make("ximagesrc", "src")
    src.set_property("display-name", a.display)
    src.set_property("use-damage", False)
    src.set_property("show-pointer", False)
    src.set_property("startx", 0)
    src.set_property("starty", 0)
    src.set_property("endx", a.width - 1)
    src.set_property("endy", a.height - 1)
    cf = Gst.ElementFactory.make("capsfilter", "cf")
    cf.set_property(
        "caps", Gst.Caps.from_string(f"video/x-raw,framerate={a.rate}/1")
    )
    sink = Gst.ElementFactory.make("fakesink", "fs")
    sink.set_property("sync", False)
    pipe = Gst.Pipeline.new("pacer")
    for e in (src, cf, sink):
        pipe.add(e)
    assert src.link(cf) and cf.link(sink), "link failed"

    step = a.stride * 4  # BGRx 4B/px
    state = {"prev": None, "n": 0}
    out = open(f"/out/fb-pacer-{a.rate}.jsonl", "w")

    def probe(_pad, info):
        buf = info.get_buffer()
        ok, m = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.PadProbeReturn.OK
        raw = m.data
        if not isinstance(raw, bytes):
            raw = raw.tobytes()
        sl = raw[1::step]  # G 通道子采样(foam/白冠敏感);bytes 切片 C 级拷贝
        h = hashlib.md5(sl).hexdigest()[:10]
        dup, mdiff, fchg = 0, 0.0, 0.0
        prev = state["prev"]
        if prev is not None:
            if h == prev[0]:
                dup = 1
            else:
                n = len(sl)
                cnt = s = 0
                for i in range(0, n, 8):
                    d = sl[i] - prev[1][i]
                    if d < 0:
                        d = -d
                    if d > 2:
                        cnt += 1
                    s += d
                mdiff = s / (n // 8 + 1)
                fchg = cnt / (n // 8 + 1)
        out.write(
            json.dumps(
                {
                    "t": round(buf.pts / 1e6, 3),
                    "wc": round(time.monotonic() % 10000, 3),
                    "h": h,
                    "dup": dup,
                    "md": round(mdiff, 3),
                    "fchg": round(fchg, 5),
                }
            )
            + "\n"
        )
        if state["n"] % 60 == 0:
            out.flush()
        state["prev"] = (h, sl)
        state["n"] += 1
        buf.unmap(m)
        return Gst.PadProbeReturn.OK

    cf.get_static_pad("sink").add_probe(Gst.PadProbeType.BUFFER, probe)
    pipe.set_state(Gst.State.PLAYING)
    time.sleep(a.seconds)
    pipe.set_state(Gst.State.NULL)
    out.close()
    print(f"done n={state['n']}", file=sys.stderr)


if __name__ == "__main__":
    main()
