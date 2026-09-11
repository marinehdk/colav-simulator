"""Exercise the assembled local source stack using frozen reference configuration."""

import argparse
import gzip
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import yaml

from colav_simulator.original_gnc.stack import NativeStack


def run(
    build: Path, source: Path, vectors: Any, env_vectors: Any, route: Any, output: Path, duration: Any, environment: Any
) -> Any:
    """Exercise a short source-timed route through the assembled backend."""
    parameters = {}
    assets = {}
    for directory in (vectors, env_vectors):
        for path in directory.glob("*.json.gz"):
            vector = json.loads(gzip.decompress(path.read_bytes()))
            parameters[vector["module"]] = vector["parameters"]
            assets.update(vector.get("assets", {}))
    local_assets = {hashlib.sha256(p.read_bytes()).hexdigest(): str(p) for p in (source / "src").rglob("*.csv")}
    mapped = {p: local_assets[h] for p, h in assets.items()}
    roots = {p.parent.name: str(p.parent) for p in (source / "src").glob("*/*/package.xml")}
    policy = yaml.safe_load((source / "src/mission/mission_supervisor/config/propulsion_policy.yaml").read_text())
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    started = time.monotonic()
    count = 0
    with (output / "trace.jsonl").open("w") as stream:

        def capture(event: Any):
            nonlocal count
            count += 1
            stream.write(json.dumps(event, separators=(",", ":")) + "\n")

        with NativeStack(
            build,
            parameters,
            roots,
            policy,
            enabled_environment=("wind", "current", "wave") if environment else (),
            asset_paths=mapped,
            trace=capture,
        ) as stack:
            value = json.loads(route.read_text())
            value["header"]["stamp"] = {"sec": stack.time_ns // 1_000_000_000, "nanosec": stack.time_ns % 1_000_000_000}
            stack.publish("/route_planning/route_plan", "ship_interfaces/msg/RoutePlan", value)
            stack.advance(duration)
            report = {
                "duration_s": stack.elapsed_s,
                "elapsed_wall_s": time.monotonic() - started,
                "events": count,
                "states": stack.states,
                "latest": stack.latest,
                "environment": environment,
            }
            (output / "result.json").write_text(json.dumps(report, indent=2))
    return {k: report[k] for k in ["duration_s", "elapsed_wall_s", "events", "environment"]}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["build", "source", "vectors", "env-vectors", "route", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--duration", type=float, default=30)
    p.add_argument("--environment", action="store_true")
    a = p.parse_args()
    print(
        json.dumps(run(a.build, a.source, a.vectors, a.env_vectors, a.route, a.output, a.duration, a.environment), indent=2)
    )
