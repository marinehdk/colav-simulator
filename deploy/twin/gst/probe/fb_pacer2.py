#!/usr/bin/env python3
"""Xvfb 帧缓冲 60Hz 采集复刻探针 v2 — 交付内容步进分类。

把 live sender 的采集行为(ximagesrc use-damage=false, 60Hz 独立时钟)复刻 60s,
逐帧记录对前1帧/前2帧的差分 + 8x8 空间块变化图,离线分类:
  normal=均匀单步 | dup=内容重复(顿) | skip=双倍步进(跳) | torn=空间撕裂(拉扯)

用法(容器内): python3 fb_pacer2.py --rate 60 --seconds 60
输出: /out/fb-pacer2-<rate>.jsonl
"""
import argparse
import hashlib
import json
import time

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--display", default=":93")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--rate", type=int, default=60)
    ap.add_argument("--seconds", type=float, default=60)
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
    pipe = Gst.Pipeline.new("pacer2")
    for e in (src, cf, sink):
        pipe.add(e)
    assert src.link(cf) and cf.link(sink), "link failed"

    # 8x8 块图:屏幕 y 分 8 带(子采样行天然按 y 分组),x 分 8 段
    stride = 32  # px
    step = stride * 4  # BGRx
    state = {"p1": None, "p2": None, "n": 0}
    out = open(f"/out/fb-pacer2-{a.rate}.jsonl", "w")

    def blockmap(sl, prev, width_blocks=8, height_blocks=8):
        # sl 为行主序子采样网格(≈60列×33行);统计每块 |Δ|>2 占比
        n = len(sl)
        bm = [[0.0] * width_blocks for _ in range(height_blocks)]
        per_row = n // height_blocks
        for i in range(0, n, 4):
            d = sl[i] - prev[i]
            if d < 0:
                d = -d
            if d <= 2:
                continue
            r = min(i // per_row, height_blocks - 1)
            c = min((i % per_row) * width_blocks // per_row, width_blocks - 1)
            bm[r][c] += 1
        denom = (n // 4) / (width_blocks * height_blocks) + 1
        return [[round(v / denom, 3) for v in row] for row in bm]

    def probe(_pad, info):
        buf = info.get_buffer()
        ok, m = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.PadProbeReturn.OK
        raw = m.data
        if not isinstance(raw, bytes):
            raw = raw.tobytes()
        sl = raw[1::step]
        h = hashlib.md5(sl).hexdigest()[:10]
        md1 = md2 = 0.0
        bm = None
        p1, p2 = state["p1"], state["p2"]
        if p1 is not None:
            if h != p1[0]:
                n = len(sl)
                s = 0
                for i in range(0, n, 8):
                    d = sl[i] - p1[1][i]
                    s += d if d >= 0 else -d
                md1 = s / (n // 8 + 1)
                if state["n"] < 2400:  # 限 bitmap 采样窗,控文件体积
                    bm = blockmap(sl, p1[1])
            if p2 is not None and h != p2[0]:
                n = len(sl)
                s = 0
                for i in range(0, n, 8):
                    d = sl[i] - p2[1][i]
                    s += d if d >= 0 else -d
                md2 = s / (n // 8 + 1)
        out.write(
            json.dumps(
                {
                    "i": state["n"],
                    "t": round(buf.pts / 1e6, 3),
                    "h": h,
                    "md1": round(md1, 3),
                    "md2": round(md2, 3),
                    "bm": bm,
                }
            )
            + "\n"
        )
        if state["n"] % 60 == 0:
            out.flush()
        state["p2"] = state["p1"]
        state["p1"] = (h, sl)
        state["n"] += 1
        buf.unmap(m)
        return Gst.PadProbeReturn.OK

    cf.get_static_pad("sink").add_probe(Gst.PadProbeType.BUFFER, probe)
    pipe.set_state(Gst.State.PLAYING)
    time.sleep(a.seconds)
    pipe.set_state(Gst.State.NULL)
    out.close()
    print(f"done n={state['n']}", file=__import__("sys").stderr)


if __name__ == "__main__":
    main()
