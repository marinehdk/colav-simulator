#!/usr/bin/env python3
"""fb_dump — 转储门控语义下的稳定帧水面区域(交付内容),供波浪相位连续性分析。

以 240Hz 采样 ximagesrc,仅当内容与上一采样一致(稳定帧,等价 sender StableGate 推送帧)
时落盘两块区域:
  A) 画面中央水带(0.45H-0.75H 全宽) — 近中场波浪
  B) 水平条带扫描(每 60px 一条 8px 高) — 按距离分层位移估计
输出: /out/fbdump/<idx>_<t_ms>_A.raw (BGRx) + meta.jsonl
用法(容器内): python3 fb_dump.py --seconds 12 [--stride 1]
"""
import argparse
import hashlib
import json
import os
import time

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--display", default=":93")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--seconds", type=float, default=12)
    ap.add_argument("--outdir", default="/out/fbdump")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

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
    cf.set_property("caps", Gst.Caps.from_string("video/x-raw,framerate=240/1"))
    sink = Gst.ElementFactory.make("fakesink", "fs")
    sink.set_property("sync", False)
    pipe = Gst.Pipeline.new("dump")
    for e in (src, cf, sink):
        pipe.add(e)
    assert src.link(cf) and cf.link(sink)

    W = a.width
    stride_px = 32  # 与 StableGate 同口径子采样
    row_a0 = int(a.height * 0.45)
    row_a1 = int(a.height * 0.75)
    state = {"prev": None, "n": 0, "saved": 0}
    meta = open(f"{a.outdir}/meta.jsonl", "w")

    def probe(_pad, info):
        buf = info.get_buffer()
        ok, m = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.PadProbeReturn.OK
        raw = m.data
        if not isinstance(raw, bytes):
            raw = raw.tobytes()
        h = hashlib.md5(raw[1::stride_px * 4]).hexdigest()[:10]
        if state["prev"] is not None and h == state["prev"]:
            # 稳定帧 = 交付帧 → 落盘
            crop = raw[row_a0 * W * 4:row_a1 * W * 4]
            fn = f"{a.outdir}/{state['saved']:05d}_{int(buf.pts/1e6)}_A.raw"
            with open(fn, "wb") as f:
                f.write(crop)
            meta.write(json.dumps({"i": state["saved"], "t": buf.pts / 1e6, "h": h}) + "\n")
            state["saved"] += 1
        state["prev"] = h
        state["n"] += 1
        buf.unmap(m)
        return Gst.PadProbeReturn.OK

    cf.get_static_pad("sink").add_probe(Gst.PadProbeType.BUFFER, probe)
    pipe.set_state(Gst.State.PLAYING)
    time.sleep(a.seconds)
    pipe.set_state(Gst.State.NULL)
    meta.close()
    print(f"done samples={state['n']} saved={state['saved']}", file=__import__("sys").stderr)


if __name__ == "__main__":
    main()
