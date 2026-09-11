"""Run independent original nodes under the same explicit period/FIFO scheduling policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import rclpy
import source_kernel_proxies as proxies
from run_embedded_campaign import run_case

from colav_simulator.original_gnc import stack as scheduling


def run(case: Path, source: Path, drivers: Path, metadata_build: Path, output: Path, domain: int) -> dict:
    """Share only scheduling and input construction; all reference algorithms are original source."""
    if output.exists():
        raise FileExistsError(output)
    os.environ.update(ROS_DOMAIN_ID=str(domain), ROS_LOCALHOST_ONLY="1")
    rclpy.init()
    probe = rclpy.create_node("coupled_reference_isolation_probe")
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        rclpy.spin_once(probe, timeout_sec=0.1)
    occupied = [name for name in probe.get_node_names() if name != probe.get_name()]
    probe.destroy_node()
    if occupied:
        rclpy.shutdown()
        raise RuntimeError(f"Coupled reference domain occupied: {occupied}")
    proxies.SETTINGS.update(source=source, drivers=drivers, output=output / "source-nodes", domain=domain)
    try:
        with (
            patch.object(scheduling, "NativeModule", proxies.CppSourceKernel),
            patch.object(scheduling, "NativePolicy", proxies.SourcePolicy),
            patch.object(scheduling, "NativeObserver", proxies.SourceObserver),
        ):
            result = run_case(case, metadata_build, source, output)
        loaded = [line for line in Path("/proc/self/maps").read_text().splitlines() if "liboriginal_gnc" in line]
        if loaded:
            raise RuntimeError("An embedded library was loaded by the independent source run")
        document = json.loads((output / "manifest.json").read_text())
        document["runtime_kind"] = "original_source_coupled"
        document["source_driver_build"] = json.loads((drivers.parents[1] / "manifest.json").read_text())
        document["embedded_library_loaded"] = False
        document["build_metadata_only"] = document.pop("build")
        document["algorithm_scope"] = (
            "original C++ ROS nodes and original Python ROS nodes; common explicit scheduler, no ROS executor timing"
        )
        document["shared_scheduler_sha256"] = hashlib.sha256(Path(scheduling.__file__).read_bytes()).hexdigest()
        document["source_python_files"] = {
            str(node.source_file): hashlib.sha256(node.source_file.read_bytes()).hexdigest() for node in proxies.PY_INSTANCES
        }
        (output / "manifest.json").write_text(json.dumps(document, indent=2))
        return result
    finally:
        for node in proxies.CPP_INSTANCES:
            if node.process.poll() is None:
                node.close()
        for node in proxies.PY_INSTANCES:
            node.close()
        rclpy.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "source", "drivers", "metadata-build", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--domain", type=int, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.case.resolve(),
                args.source.resolve(),
                args.drivers.resolve(),
                args.metadata_build.resolve(),
                args.output.resolve(),
                args.domain,
            )
        ),
        flush=True,
    )
