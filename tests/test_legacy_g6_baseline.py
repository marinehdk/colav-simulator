from __future__ import annotations

import json
from pathlib import Path

from colav_simulator.legacy_g6_baseline import (
    PINNED_BASELINE_COMMIT,
    BaselineMismatchError,
    capture_baseline,
    compare_baseline,
    main,
)

FIXTURE = Path(__file__).parent / "fixtures" / "gnc_g6" / "legacy-baseline-v1.json"


def test_committed_baseline_is_pinned_and_self_consistent() -> None:
    baseline = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert baseline["schema_version"] == "gnc-g6-legacy-baseline.v1"
    assert baseline["pinned_commit"] == PINNED_BASELINE_COMMIT
    assert baseline["main_checkout_dirty_work_included"] is False
    assert baseline["acceptance_claim"] == "G6 legacy regression characterization; A1 only"
    assert baseline["test_suite"]["file_count"] > 0
    assert baseline["reference_scenarios"]
    assert all(case["per_tick_sha256"] for case in baseline["reference_scenarios"])
    assert baseline["expected_output_sha256"]

    compare_baseline(FIXTURE)


def test_capture_reproduces_committed_baseline(tmp_path: Path) -> None:
    output = tmp_path / "captured.json"

    captured = capture_baseline(output)

    assert captured == json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert json.loads(output.read_text(encoding="utf-8")) == captured


def test_compare_reports_content_addressed_mismatch(tmp_path: Path) -> None:
    modified = json.loads(FIXTURE.read_text(encoding="utf-8"))
    modified["reference_scenarios"][0]["per_tick_sha256"][0] = "0" * 64
    fixture = tmp_path / "modified.json"
    fixture.write_text(json.dumps(modified), encoding="utf-8")

    try:
        compare_baseline(fixture)
    except BaselineMismatchError as exc:
        assert "expected_output_sha256" in str(exc)
    else:
        raise AssertionError("modified baseline unexpectedly matched")


def test_cli_capture_and_compare(tmp_path: Path) -> None:
    output = tmp_path / "captured.json"

    assert main(["capture", "--output", str(output)]) == 0
    assert main(["compare", "--baseline", str(output)]) == 0
