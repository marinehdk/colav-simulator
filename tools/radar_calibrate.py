"""Inspect normalized radar recordings or estimate biases from reference pairs.

Examples:
  .venv/bin/python tools/radar_calibrate.py inspect recording.jsonl --output report.json
  .venv/bin/python tools/radar_calibrate.py fit references.json --output report.json

PCAP/vendor data must first be decoded by its documented vendor-specific decoder;
this tool does not guess proprietary packet layouts or create missing references.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from colav_simulator.core.radar_calibration import estimate_bias, inspect_recording


def main():
    """Validate evidence or estimate biases without applying runtime changes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "fit"))
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "inspect":
        report = inspect_recording(args.input)
    else:
        data = json.loads(args.input.read_text())
        report = estimate_bias(data["pairs"], source_kind=data["source_kind"], provenance=data["provenance"])
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(report["calibration_status"])


if __name__ == "__main__":
    main()
