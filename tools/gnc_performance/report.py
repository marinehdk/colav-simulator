"""Render aggregate Issue #54 benchmark JSON as a reviewable Markdown table."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _format_ns(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.3f} ms"
    if value >= 1_000:
        return f"{value / 1_000:.3f} us"
    return f"{value:.1f} ns"


def render_report(data: dict[str, Any], result_sha256: str | None = None) -> str:
    """Render benchmark evidence with explicit claim and decision ceilings."""
    provenance = data["provenance"]
    rows = data["rows"]
    lines = [
        "# Issue #54 modular GNC performance evidence",
        "",
        f"- Schema: `{data['schema_version']}`",
        f"- Claim ceiling: `{data['claim_ceiling']}`",
        f"- Commit: `{provenance.get('commit_head')}`",
        f"- Platform: `{provenance.get('os')}`, `{provenance.get('kernel')}`, `{provenance.get('architecture')}`",
        f"- Python: `{provenance.get('python_executable')}` / `{provenance.get('python_version')}`",
        f"- uv.lock SHA-256: `{provenance.get('uv_lock_sha256')}`",
        f"- Dependency freeze SHA-256: `{provenance.get('dependency_freeze_sha256')}`",
        f"- Harness config SHA-256: `{provenance.get('harness_config_hash')}`",
        f"- Result SHA-256: `{result_sha256 or provenance.get('result_sha256')}`",
        f"- CPU affinity: `{provenance.get('cpu_affinity_status')}`",
        "",
        "## Contract",
        "",
        "The harness directly instantiates `AnalyticEnvironmentField`, `EnvironmentalLoadModel`, "
        "`Generic3DOFPlant`, and scheduler-owned `rk4_step`. It excludes GUI, legacy simulation, "
        "COLAV, and adapter overhead. Each measured simulated second is 50 base ticks × 4 RK4 "
        "stages = 200 RHS evaluations per ship per simulated second. No simulation state uses wall time.",
        "",
        "## Matrix results",
        "",
        (
            "| Ships | Harmonics | Median RTF/ship | RHS p50 | RHS p95 | RK4 step p50 | "
            "RK4 step p95 | Peak RSS | RHS identity | Repeat digest |"
        ),
        "|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['ships']} | {row['harmonics']} | {row['median_rtf_per_ship']:.3f} | "
            f"{_format_ns(row['median_rhs_latency_ns']['p50'])} | "
            f"{_format_ns(row['median_rhs_latency_ns']['p95'])} | "
            f"{_format_ns(row['median_rk4_step_latency_ns']['p50'])} | "
            f"{_format_ns(row['median_rk4_step_latency_ns']['p95'])} | "
            f"{row['peak_rss_bytes'] / (1024 * 1024):.2f} MiB | "
            f"{row['rhs_count_identity']} | {row['deterministic_output_digest']} |"
        )
    lines.extend(
        [
            "",
            "## Harmonic scaling ratios",
            "",
            "Ratios are measured ratios relative to the 8-harmonic row for the same ship count; "
            "they are not a fitted complexity claim.",
            "",
            "| Ships | From | To | RHS p95 ratio | RTF ratio |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for item in data["harmonic_scaling"]:
        lines.append(
            f"| {item['ships']} | {item['from_harmonics']} | {item['to_harmonics']} | "
            f"{item['rhs_p95_ratio']:.3f} | {item['rtf_ratio']:.3f} |"
        )
    proposal = data["threshold_proposal"]
    lines.extend(
        [
            "",
            "## Threshold proposal (PROPOSED_NOT_APPROVED)",
            "",
            "No numeric threshold is approved by this artifact. Issue #54 requires approval in the issue "
            "before subsequent slices; absence remains NO-GO for subsequent slices.",
            "",
            "Options recorded without decision:",
            "",
            *[f"1. {option}" for option in proposal["options"]],
            "",
            (f"- Required 20-ship representative RTF floor: `{proposal['required_20_ship_representative_row_rtf_floor']}`"),
            (
                "- RHS reference budget: "
                f"`{proposal['rhs_p95_budget_relative_to_5ms']['per_ship_serial_budget_ms']} ms` per serial RHS budget"
            ),
            f"- Memory ceiling: `{proposal['memory_ceiling_bytes']}`",
            f"- Harmonic scaling guard: `{proposal['harmonic_scaling_guard']}`",
            "",
            "## Boundaries and remaining blockers",
            "",
            "- This is performance characterization and A2 blocker evidence only.",
            "- It is not plant parity, vessel validation, COLAV, SIL, HIL, or sea-trial evidence.",
            "- A2 parity remains blocked pending the performance decision; issue #55 remains blocked.",
            "- CPU affinity/governor was uncontrolled unless separately recorded by the execution environment.",
            (
                "- Per-RHS latency is a stage-batch wall-time attribution divided by four; "
                "RK4 step timing is directly measured."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Render Markdown from a benchmark result JSON file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    data = json.loads(args.input.read_text(encoding="utf-8"))
    result_sha = hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.write_text(render_report(data, result_sha), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
