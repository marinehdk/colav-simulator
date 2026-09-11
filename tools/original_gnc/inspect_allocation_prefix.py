"""Read exact allocator state drift without changing the frozen comparison gates."""

import argparse
import gzip
import json
from pathlib import Path

from colav_simulator.original_gnc.native import NativeModule

p = argparse.ArgumentParser()
p.add_argument("--build", type=Path, required=True)
p.add_argument("--vector", type=Path, required=True)
p.add_argument("--source", type=Path, required=True)
p.add_argument("--stop", type=int, required=True)
a = p.parse_args()
v = json.load(gzip.open(a.vector, "rt"))
ex = json.load(open(a.build / "extraction.json"))
roots = {p.parent.name: str(p.parent) for p in (a.source / "src").glob("*/*/package.xml")}
opt = {
    "replay_clocks": v["clock_reads"],
    "omitted_log_clock_sites": ex["modules"][v["module"]]["omitted_log_clock_sites"],
    "package_roots": roots,
}
first = False
with NativeModule(a.build, v["module"], v["parameters"], opt) as module:
    for i, c in enumerate(v["calls"]):
        actual = module.invoke(c["function"], c["input"], 0)
        if not first:
            for j, (x, y) in enumerate(zip(c["state"]["actuators"], actual["state"]["actuators"], strict=True)):
                for key in ["last_force_n", "last_angle_rad"]:
                    if x[key] != y[key]:
                        print(
                            "FIRST",
                            i,
                            c["function"],
                            j,
                            key,
                            x[key],
                            y[key],
                            float(x[key]).hex(),
                            float(y[key]).hex(),
                            flush=True,
                        )
                        first = True
                        break
                if first:
                    break
        if i >= a.stop - 2:
            print("NEAR", i, c["function"], actual["state"], flush=True)
        if i >= a.stop:
            break
