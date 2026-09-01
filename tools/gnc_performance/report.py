"""Render v2 Issue #54 benchmark JSON as reviewable Markdown evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _format_ns(value: float) -> str:
    """Format nanoseconds with an explicit human-readable unit."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.3f} ms"
    if value >= 1_000:
        return f"{value / 1_000:.3f} us"
    return f"{value:.1f} ns"


def render_report(data: dict[str, Any], result_file_sha256: str | None = None) -> str:
    """Render corrected metrics, provenance, threshold proposal, and boundaries."""
    provenance = data["provenance"]
    lines = [
        "# Issue #54 modular GNC performance evidence",
        "",
        f"- Schema: `{data['schema_version']}`",
        f"- Claim ceiling: `{data['claim_ceiling']}`",
        f"- Execution source commit H: `{provenance.get('execution_source_commit')}`",
        f"- Execution source archive SHA-256: `{provenance.get('execution_source_archive_sha256')}`",
        f"- Execution source manifest SHA-256: `{provenance.get('execution_source_manifest_sha256')}`",
        f"- Execution source dirty: `{provenance.get('execution_source_dirty')}`",
        f"- Platform: `{provenance.get('os')}`, `{provenance.get('kernel')}`, `{provenance.get('architecture')}`",
        f"- Python: `{provenance.get('python_executable')}` / `{provenance.get('python_version')}`",
        f"- uv.lock SHA-256: `{provenance.get('uv_lock_sha256')}`",
        f"- Dependency freeze SHA-256: `{provenance.get('dependency_freeze_sha256')}`",
        f"- Harness config SHA-256: `{provenance.get('harness_config_hash')}`",
        f"- Input SHA-256: `{provenance.get('input_hash')}`",
        f"- `result_file_sha256`: `{result_file_sha256}`",
        f"- `payload_sha256`: `{provenance.get('payload_sha256')}`",
        f"- CPU affinity: `{provenance.get('cpu_affinity_status')}`",
        "",
        "## Contract and traceability",
        "",
        "Direct path: `AnalyticEnvironmentField` + `EnvironmentalLoadModel` + `Generic3DOFPlant` + "
        "scheduler-owned `rk4_step`; GUI, legacy simulation, COLAV, and adapters excluded. "
        "Fixed 50 Hz × RK4 × 4 stages = 200 direct RHS evaluations per ship per simulated second. "
        "Each k1/k2/k3/k4 sample directly times stage-specific environment query, load model, and plant RHS. "
        "Parent RSS monitoring is outside worker timing loop.",
        "",
        f"Authoritative RA-03: `{data['traceability']['authoritative_ra03']['path']}`, "
        f"section `{data['traceability']['authoritative_ra03']['section']}`.",
        "",
        "## Matrix results",
        "",
        "Scenario RTF = common-axis simulated seconds / wall seconds. Aggregate ship-s/s = ships × "
        "scenario simulated seconds / wall seconds. Percentiles below pool direct samples across all three repeats.",
        "",
        (
            "| Ships | Harmonics | Scenario RTF median (min/max/CV) | Aggregate ship-s/s | k1 p95 | "
            "k2 p95 | k3 p95 | k4 p95 | Pooled RHS p95 | RK4 step p95 | Peak current RSS | "
            "Max row delta RSS |"
        ),
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in data["rows"]:
        rtf = row["scenario_rtf"]
        stage = row["direct_stage_latency_ns_pooled_across_repeats"]
        lines.append(
            f"| {row['ships']} | {row['harmonics']} | "
            f"{rtf['median']:.3f} ({rtf['min']:.3f}/{rtf['max']:.3f}/{rtf['cv']:.3f}) | "
            f"{row['aggregate_ship_seconds_per_wall_second']:.3f} | "
            f"{_format_ns(stage['k1']['p95'])} | {_format_ns(stage['k2']['p95'])} | "
            f"{_format_ns(stage['k3']['p95'])} | {_format_ns(stage['k4']['p95'])} | "
            f"{_format_ns(row['direct_pooled_rhs_latency_ns_pooled_across_repeats']['p95'])} | "
            f"{_format_ns(row['rk4_step_latency_ns_pooled_across_repeats']['p95'])} | "
            f"{row['peak_current_rss_bytes'] / 1048576:.2f} MiB | {row['max_delta_current_rss_bytes'] / 1048576:.2f} MiB |"
        )
    lines.extend(
        [
            "",
            "## Harmonic scaling",
            "",
            "Ratios are descriptive measurements relative to the 8-harmonic row for each ship count; "
            "no complexity model is claimed.",
            "",
            "| Ships | From | To | Direct pooled RHS p95 ratio | Scenario RTF ratio |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for item in data["harmonic_scaling"]:
        lines.append(
            f"| {item['ships']} | {item['from_harmonics']} | {item['to_harmonics']} | "
            f"{item['direct_pooled_rhs_p95_ratio']:.3f} | {item['scenario_rtf_ratio']:.3f} |"
        )
    proposal = data["threshold_proposal"]
    lines.extend(
        [
            "",
            "## Threshold proposal — PROPOSED_NOT_APPROVED",
            "",
            "No GO/NO-GO decision is made here. These candidate thresholds require issue-owner approval.",
            "",
            "| Candidate | Limit | Observed representative 20 ships/32 harmonics | Result |",
            "|---|---:|---:|:---:|",
        ]
    )
    for name, check in proposal["checks"].items():
        lines.append(f"| {name} | {check['limit']} | {check['observed']:.6g} | {check['pass']} |")
    lines.extend(
        [
            "",
            "- Representative row: 20 ships / 32 harmonics.",
            "- Scenario RTF floor: 1.00.",
            "- Direct pooled RHS p95 ceiling: 0.25 ms for 20-ship serial aggregate; separate per-ship reference: 5 ms.",
            "- Memory ceilings: 128 MiB peak current RSS and 64 MiB per-row current-RSS delta.",
            "- Harmonic guards: 8→32 ≤ 2.00 and 8→128 ≤ 5.25 direct pooled RHS p95 ratio.",
            "- Stress row: 20 ships / 128 harmonics, candidate Scenario RTF floor 0.25; not representative GO row.",
            "- Decision options recorded only: Python GO; remediation-vectorization; same-contract native adapter.",
            "",
            "## Boundaries",
            "",
            "- Performance characterization and A2 blocker evidence only.",
            "- No plant parity, vessel validation, COLAV, SIL, HIL, or sea-trial claim.",
            "- A2 remains blocked pending the performance decision; #55 remains blocked.",
            "- Rollback point: `17c075b0cb8fd3d13a1f5cc9294e319fe1bd2c98`.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Render Markdown from a v2 benchmark result JSON file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    data = json.loads(args.input.read_text(encoding="utf-8"))
    result_file_sha256 = hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.write_text(render_report(data, result_file_sha256), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
