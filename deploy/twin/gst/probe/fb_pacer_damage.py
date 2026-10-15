#!/usr/bin/env python3
"""damage 驱动采集模式验证探针。

use-damage=true 时 ximagesrc 由 X damage 事件驱动采集 — 若有效,
采集节奏=渲染 present 时刻(事件驱动,无时钟竞态)。
输出同 fb_pacer 的行格式,便于同一套分析。

用法(容器内): python3 fb_pacer_damage.py --seconds 30 [--rate 240]
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
    ap.add_argument("--rate", type=int, default=240, help="damage 模式的速率上限")
    ap.add_argument("--seconds", type=float, default=30)
    a = ap.parse_args()

    Gst.init(None)
    src = Gst.ElementFactory.make("ximagesrc", "src")
    src.set_property("display-name", a.display)
    src.set_property("use-damage", True)  # ← 唯一差异:事件驱动
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
    pipe = Gst.Pipeline.new("pacer3")
    for e in (src, cf, sink):
        pipe.add(e)
    assert src.link(cf) and cf.link(sink), "link failed"

    step = 32 * 4
    state = {"prev": None, "n": 0}
    out = open(f"/out/fb-pacer-dmg-{a.rate}.jsonl", "w")

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
        dup, mdiff = 0, 0.0
        prev = state["prev"]
        if prev is not None and prev[0] != h:
            n = len(sl)
            s = 0
            for i in range(0, n, 8):
                d = sl[i] - prev[1][i]
                s += d if d >= 0 else -d
            mdiff = s / (n // 8 + 1)
        elif prev is not None:
            dup = 1
        out.write(
            json.dumps(
                {
                    "i": state["n"],
                    "t": round(buf.pts / 1e6, 3),
                    "h": h,
                    "dup": dup,
                    "md": round(mdiff, 3),
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
    print(f"done n={state['n']}", file=__import__("sys").stderr)


if __name__ == "__main__":
    main()
