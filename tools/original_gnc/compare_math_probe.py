"""Apply predeclared dimensional rules to independent plant-math observations."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def compare(inputs: Path, reference: Path, native: Path, output: Path) -> dict:  # noqa: C901
    """Require every probe, matrix entry, derivative and RK stage to match."""
    request = json.loads(inputs.read_text())
    rules = request["comparison_rules"]
    expected = [json.loads(line) for line in reference.open()]
    actual = [json.loads(line) for line in native.open()]
    differences = []
    maxima = {}
    checked = 0
    if len(expected) != len(request["cases"]) or len(actual) != len(expected):
        differences.append(
            {"kind": "probe_count", "expected": len(request["cases"]), "reference": len(expected), "native": len(actual)}
        )

    def rule(name: str, path: tuple[int, ...]) -> tuple[float, float, str]:
        if name in ("M", "C"):
            angular = sum(i >= 2 for i in path)
            entry = rules[name]
            return entry["absolute_by_angular_indices"][angular], entry["relative"], entry["units"][angular]
        if name == "M_inverse":
            return rules[name]["absolute"], rules[name]["relative"], "inverse-mass"
        if name == "decomposition_residual":
            return rules[name]["absolute"], rules[name]["relative"], "acceleration residual"
        if name in ("D", "C_nu", "restoring_roll_nm"):
            axis = path[0] if path else 2
            entry = rules["forces"]
            return entry["absolute"][axis], entry["relative"], "N" if axis < 2 else "N.m"
        entry = rules["velocity" if name in ("rk_result", "nu_k2", "nu_k3", "nu_k4") else "acceleration"]
        axis = path[0]
        return (
            entry["absolute"][axis],
            entry["relative"],
            ("velocity" if name.startswith(("rk_", "nu_")) else "acceleration"),
        )

    def visit(left: object, right: object, name: str, path: tuple[int, ...], case_id: int) -> None:
        nonlocal checked
        if isinstance(left, list):
            if not isinstance(right, list) or len(left) != len(right):
                differences.append({"case_id": case_id, "field": name, "kind": "shape"})
                return
            for i, (a, b) in enumerate(zip(left, right, strict=True)):
                visit(a, b, name, path + (i,), case_id)
            return
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (left, right)):
            differences.append({"case_id": case_id, "field": name, "path": path, "kind": "nonfinite-or-missing"})
            return
        absolute, relative, unit = rule(name, path)
        checked += 1
        error = abs(right - left)
        maxima[unit] = max(maxima.get(unit, 0.0), error)
        if error > absolute + relative * abs(left):
            differences.append(
                {"case_id": case_id, "field": name, "path": path, "expected": left, "actual": right, "error": error}
            )
        if name == "decomposition_residual" and max(abs(left), abs(right)) > absolute:
            differences.append({"case_id": case_id, "field": name, "path": path, "kind": "component-reconstruction-failed"})

    required = {
        "case_id",
        "M",
        "M_inverse",
        "C",
        "D",
        "C_nu",
        "restoring_roll_nm",
        "rhs",
        "decomposition_residual",
        "k1",
        "k2",
        "k3",
        "k4",
        "nu_k2",
        "nu_k3",
        "nu_k4",
        "rk_result",
    }
    for case, ref, value in zip(request["cases"], expected, actual, strict=True):
        if set(ref) != required or set(value) != required or not (ref["case_id"] == value["case_id"] == case["case_id"]):
            differences.append({"kind": "probe_identity_or_fields", "case_id": case["case_id"]})
            continue
        for name in required - {"case_id"}:
            visit(ref[name], value[name], name, (), case["case_id"])
        for origin, record in (("reference", ref), ("native", value)):
            for axis in range(4):
                rebuilt = case["nu"][axis] + (case["dt_s"] / 6.0) * (
                    record["k1"][axis] + 2.0 * record["k2"][axis] + 2.0 * record["k3"][axis] + record["k4"][axis]
                )
                tolerance = rules["velocity"]["absolute"][axis] + rules["velocity"]["relative"] * abs(rebuilt)
                if abs(rebuilt - record["rk_result"][axis]) > tolerance:
                    differences.append(
                        {"kind": "RK-stage-reconstruction", "origin": origin, "case_id": case["case_id"], "axis": axis}
                    )
    result = {
        "passed": not differences and checked > 0,
        "probe_count": len(expected),
        "scalar_fields_checked": checked,
        "max_error_by_unit": maxima,
        "first_difference": differences[0] if differences else None,
        "difference_count": len(differences),
        "input_sha256": hashlib.sha256(inputs.read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "native_sha256": hashlib.sha256(native.read_bytes()).hexdigest(),
        "comparison_rules": rules,
        "scope": (
            "M read from actual instances; C/D expression decomposition checked against actual RHS; "
            "native RHS/RK call the packaged shared library"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "reference", "native", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.inputs, args.reference, args.native, args.output)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
