from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    case = baseline["reference_scenarios"][0]
    assert case["execution_chain"] == {
        "controller_type": "PassThroughCS",
        "model_type": "KinematicCSOG",
        "modular_path_selected": False,
        "ship_type": "Ship",
    }
    assert case["error_semantics"]["invalid_initial_state"]["type"] == "ValueError"
    assert baseline["expected_output_sha256"]

    compare_baseline(FIXTURE)


def test_capture_reproduces_committed_baseline_from_isolated_pinned_checkout(tmp_path: Path) -> None:
    output = tmp_path / "captured.json"

    captured = capture_baseline(output)

    assert captured == json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert json.loads(output.read_text(encoding="utf-8")) == captured
    assert captured["execution_identity"] == {
        "commit": PINNED_BASELINE_COMMIT,
        "isolation": "git_archive",
    }
    assert "test_sha256" not in captured["reference_scenarios"][0]


def test_current_checkout_cannot_claim_pinned_execution_identity(tmp_path: Path) -> None:
    output = tmp_path / "captured.json"

    with pytest.raises(BaselineMismatchError, match="execution identity"):
        capture_baseline(output, execution_root=Path(__file__).resolve().parents[1])

    assert not output.exists()


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


def test_feature_head_compare_uses_pinned_fixture_without_regeneration(tmp_path: Path) -> None:
    fixture = tmp_path / "baseline.json"
    fixture.write_bytes(FIXTURE.read_bytes())
    before = fixture.read_bytes()

    compare_baseline(fixture)

    assert fixture.read_bytes() == before
