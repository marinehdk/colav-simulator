from __future__ import annotations

import json
import math
from dataclasses import replace

import numpy as np
import pytest

from colav_simulator.core.colav.prediction_evidence import (
    ArtifactState,
    EvidenceEnvelope,
    EvidenceEvent,
    EvidenceEventType,
    EvidenceTrackKey,
    EvidenceVerificationLevel,
    OccurrenceId,
    OptimizationIntervalReference,
    OwnshipPrediction,
    PredictionEvidenceRecord,
    PredictionGrid,
    PredictionPurpose,
    RuntimeAppliedReference,
    TargetPredictionEvidence,
    TerminalOutcome,
    canonical_bytes,
    inline_projection,
    prediction_evidence_from_dict,
    reduce_evidence,
    verify_evidence,
    verify_evidence_document,
)


def _record() -> PredictionEvidenceRecord:
    grid = PredictionGrid(intervals=2, dt_s=15.0)
    ownship = OwnshipPrediction(
        grid=grid,
        north_m=np.array([0.0, 150.0, 150.0 + 150.0 * math.cos(0.1)]),
        east_m=np.array([0.0, 0.0, 150.0 * math.sin(0.1)]),
        heading_rad=np.array([0.0, 0.0, 0.1]),
        speed_mps=np.array([10.0, 10.0, 10.0]),
        state_sources=("MEASURED", "IPOPT_INTEGRATED", "IPOPT_INTEGRATED"),
        interval_references=(
            OptimizationIntervalReference(0, 0.0, 15.0, 0.0, 10.0, 0, 2),
            OptimizationIntervalReference(1, 15.0, 30.0, 0.1, 10.0, 1, 3),
        ),
    )
    return PredictionEvidenceRecord(
        algorithm_id="mid_mpc_ipopt",
        candidate_hash="candidate-abc",
        acceptance_hash="acceptance-def",
        ownship=ownship,
        target_predictions=(),
        acceptance={"accepted": True, "mandatory_failures": []},
        solver={"backend": "ipopt", "return_status": "Solve_Succeeded"},
    )


def _event(
    seq: int,
    kind: EvidenceEventType,
    *,
    outcome: TerminalOutcome | None = None,
    semantic_hash: str | None = None,
    payload: dict[str, object] | None = None,
) -> EvidenceEvent:
    return EvidenceEvent(
        occurrence_id=OccurrenceId("run-1", 0, seq),
        event_type=kind,
        sim_time_s=float(seq),
        semantic_hash=semantic_hash,
        terminal_outcome=outcome,
        payload={} if payload is None else payload,
    )


def test_prediction_record_has_exact_grid_semantics_and_stable_hash() -> None:
    record = _record()
    reordered = replace(record, solver={"return_status": "Solve_Succeeded", "backend": "ipopt"})

    assert record.ownship.grid.intervals == 2
    assert record.ownship.grid.state_samples == 3
    assert record.ownship.grid.duration_s == 30.0
    assert record.ownship.interval_references[-1].end_s == 30.0
    assert record.ownship.state_sources[0] == "MEASURED"
    ownship_document = record.ownship.to_dict()
    assert ownship_document["state_provenance"][0]["generating_interval"] is None
    assert ownship_document["state_provenance"][-1]["generating_interval"] == 1
    assert ownship_document["control_reference_count"] == 2
    assert ownship_document["terminal_knot_control_reference"] is None
    assert record.semantic_hash == reordered.semantic_hash
    assert json.loads(canonical_bytes(record.to_dict()))["canonicalizer_id"] == "colav.python-json@1"


def test_prediction_record_rejects_nonfinite_and_interval_knot_mismatch() -> None:
    record = _record()

    with pytest.raises(ValueError, match="finite"):
        replace(record.ownship, east_m=np.array([0.0, math.nan, 1.0]))
    with pytest.raises(ValueError, match="interval references"):
        replace(record.ownship, interval_references=record.ownship.interval_references[:1])
    with pytest.raises(ValueError, match="read-only"):
        record.ownship.north_m[0] = 1.0
    with pytest.raises(TypeError):
        record.acceptance["accepted"] = False
    assert canonical_bytes({"zero": -0.0}) == b'{"zero":0.0}'


def test_runtime_applied_reference_reports_linear_interpolation_without_changing_ocp_reference() -> None:
    applied = RuntimeAppliedReference.linear(
        elapsed_s=7.5,
        dt_s=15.0,
        heading_rad=(0.0, 0.2),
        speed_mps=(8.0, 10.0),
    )

    assert applied.policy == "LINEAR_INTERPOLATION"
    assert applied.heading_rad == pytest.approx(0.1)
    assert applied.speed_mps == pytest.approx(9.0)
    assert applied.interval_index == 0


def test_selected_target_predictions_must_reconcile_across_nlp_and_l4_purposes() -> None:
    key = EvidenceTrackKey(7, 2)
    nlp = TargetPredictionEvidence(
        key=key,
        purpose=PredictionPurpose.NLP,
        reference_time_s=10.0,
        model="constant_velocity",
        north_m=np.array([0.0, 1.0, 2.0]),
        east_m=np.array([5.0, 5.0, 5.0]),
        admitted_to_nlp=True,
        solver_slot=0,
    )
    mismatched_l4 = replace(
        nlp,
        purpose=PredictionPurpose.L4_SAFETY,
        north_m=np.array([0.0, 1.0, 2.1]),
    )

    with pytest.raises(ValueError, match="reconciliation mismatch"):
        replace(_record(), target_predictions=(nlp, mismatched_l4))
    with pytest.raises(ValueError, match="L4_SAFETY"):
        replace(_record(), target_predictions=(nlp,))


def test_reducer_distinguishes_latest_attempt_active_receipt_and_artifact_state() -> None:
    record = _record()
    events = (
        _event(0, EvidenceEventType.CYCLE_STARTED),
        _event(1, EvidenceEventType.CANDIDATE_PRODUCED, semantic_hash=record.semantic_hash),
        _event(
            2,
            EvidenceEventType.PLAN_COMMITTED,
            outcome=TerminalOutcome.COMMITTED,
            semantic_hash=record.semantic_hash,
            payload={"receipt_hash": "receipt-1"},
        ),
        _event(3, EvidenceEventType.COMMAND_APPLIED, semantic_hash=record.semantic_hash),
        _event(
            4,
            EvidenceEventType.ARTIFACT_QUEUED,
            semantic_hash=record.semantic_hash,
            payload={"state": ArtifactState.QUEUED},
        ),
        _event(5, EvidenceEventType.CYCLE_STARTED),
        _event(6, EvidenceEventType.PLAN_REJECTED, outcome=TerminalOutcome.REJECTED),
    )

    timeline = reduce_evidence(events)

    assert timeline.latest_terminal_outcome is TerminalOutcome.REJECTED
    assert timeline.active_semantic_hash is None
    assert timeline.last_committed_semantic_hash == record.semantic_hash
    assert timeline.last_committed_executable is False
    assert timeline.artifact_state is ArtifactState.QUEUED


def test_reducer_does_not_apply_old_artifact_completion_to_new_candidate() -> None:
    prior = _record()
    current = replace(prior, candidate_hash="candidate-current")
    events = (
        _event(0, EvidenceEventType.CYCLE_STARTED),
        _event(1, EvidenceEventType.CANDIDATE_PRODUCED, semantic_hash=prior.semantic_hash),
        _event(
            2,
            EvidenceEventType.PLAN_COMMITTED,
            outcome=TerminalOutcome.COMMITTED,
            semantic_hash=prior.semantic_hash,
            payload={"receipt_hash": "receipt-1"},
        ),
        _event(3, EvidenceEventType.COMMAND_APPLIED, semantic_hash=prior.semantic_hash),
        _event(4, EvidenceEventType.ARTIFACT_QUEUED, semantic_hash=prior.semantic_hash),
        _event(5, EvidenceEventType.CYCLE_STARTED),
        _event(6, EvidenceEventType.CANDIDATE_PRODUCED, semantic_hash=current.semantic_hash),
        _event(
            7,
            EvidenceEventType.PLAN_COMMITTED,
            outcome=TerminalOutcome.COMMITTED,
            semantic_hash=current.semantic_hash,
            payload={"receipt_hash": "receipt-2"},
        ),
        _event(8, EvidenceEventType.COMMAND_APPLIED, semantic_hash=current.semantic_hash),
        _event(9, EvidenceEventType.ARTIFACT_QUEUED, semantic_hash=current.semantic_hash),
        _event(10, EvidenceEventType.ARTIFACT_COMPLETE, semantic_hash=prior.semantic_hash),
    )

    timeline = reduce_evidence(events)

    assert timeline.active_semantic_hash == current.semantic_hash
    assert timeline.artifact_state is ArtifactState.QUEUED


def test_reducer_rejects_duplicate_or_out_of_order_occurrences() -> None:
    duplicate = (
        _event(0, EvidenceEventType.CYCLE_STARTED),
        _event(0, EvidenceEventType.PLAN_FAILED, outcome=TerminalOutcome.FAILED),
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        reduce_evidence(duplicate)


def test_reducer_rejects_missing_causal_parent() -> None:
    events = (
        _event(0, EvidenceEventType.CYCLE_STARTED),
        replace(
            _event(1, EvidenceEventType.INPUT_VALIDATED),
            caused_by=OccurrenceId("run-1", 0, 99),
        ),
    )

    with pytest.raises(ValueError, match="causal parent"):
        reduce_evidence(events)


def test_reducer_rejects_command_after_failed_candidate() -> None:
    events = (
        _event(0, EvidenceEventType.CYCLE_STARTED),
        _event(1, EvidenceEventType.PLAN_REJECTED, outcome=TerminalOutcome.REJECTED),
        _event(2, EvidenceEventType.COMMAND_APPLIED, semantic_hash=_record().semantic_hash),
    )

    with pytest.raises(ValueError, match="COMMAND_APPLIED requires"):
        reduce_evidence(events)


def test_reducer_requires_command_for_committed_authority() -> None:
    record = _record()
    events = (
        _event(0, EvidenceEventType.CYCLE_STARTED),
        _event(
            1,
            EvidenceEventType.PLAN_COMMITTED,
            outcome=TerminalOutcome.COMMITTED,
            semantic_hash=record.semantic_hash,
            payload={"receipt_hash": "receipt-1"},
        ),
    )

    with pytest.raises(ValueError, match="committed or held cycle requires COMMAND_APPLIED"):
        reduce_evidence(events)


def test_inline_projection_preserves_mandatory_failures_before_advisory_details() -> None:
    record = replace(
        _record(),
        acceptance={
            "accepted": False,
            "mandatory_failures": [{"code": "SAFETY_SWEPT_CLEARANCE", "target_key": [7, 2], "clearance_m": 12.0}],
            "advisory": ["x" * 3000],
        },
    )

    projection = inline_projection(record, capacity_bytes=900)
    encoded = canonical_bytes(projection)

    assert len(encoded) <= 900
    assert projection["accepted"] is False
    assert projection["mandatory_failures"][0]["code"] == "SAFETY_SWEPT_CLEARANCE"
    assert projection["truncated"] is True


def test_bounded_envelope_keeps_artifact_reference_with_inline_verdict() -> None:
    envelope = EvidenceEnvelope(_record())
    artifact = {"status": "QUEUED", "sha256": "a" * 64, "relative_path": "artifacts/mid_mpc/a.json.gz"}

    projection = envelope.to_inline_dict(artifact_reference=artifact)

    assert len(canonical_bytes(projection)) <= 8192
    assert projection["artifact_reference"] == artifact
    assert projection["inline"]["accepted"] is True


def test_public_verifier_reports_hash_schema_and_timeline_tampering() -> None:
    record = _record()
    events = (
        _event(0, EvidenceEventType.CYCLE_STARTED),
        _event(1, EvidenceEventType.CANDIDATE_PRODUCED, semantic_hash=record.semantic_hash),
        _event(
            2,
            EvidenceEventType.PLAN_COMMITTED,
            semantic_hash=record.semantic_hash,
            outcome=TerminalOutcome.COMMITTED,
            payload={"receipt_hash": "receipt-1"},
        ),
        _event(3, EvidenceEventType.COMMAND_APPLIED, semantic_hash=record.semantic_hash),
    )

    valid = verify_evidence(record, events)
    tampered = verify_evidence(record, events, expected_semantic_hash="0" * 64)

    assert valid.highest_verified_level is EvidenceVerificationLevel.RUNTIME_AUTHORITY
    assert valid.valid is True
    assert tampered.valid is False
    assert tampered.failures == ("SEMANTIC_HASH_MISMATCH",)


def test_public_verifier_accepts_current_record_after_prior_committed_cycle() -> None:
    prior = _record()
    current = replace(prior, candidate_hash="candidate-current")
    events = (
        _event(0, EvidenceEventType.CYCLE_STARTED),
        _event(1, EvidenceEventType.CANDIDATE_PRODUCED, semantic_hash=prior.semantic_hash),
        _event(
            2,
            EvidenceEventType.PLAN_COMMITTED,
            outcome=TerminalOutcome.COMMITTED,
            semantic_hash=prior.semantic_hash,
            payload={"receipt_hash": "receipt-1"},
        ),
        _event(3, EvidenceEventType.COMMAND_APPLIED, semantic_hash=prior.semantic_hash),
        _event(4, EvidenceEventType.CYCLE_STARTED),
        _event(5, EvidenceEventType.CANDIDATE_PRODUCED, semantic_hash=current.semantic_hash),
        _event(
            6,
            EvidenceEventType.PLAN_COMMITTED,
            outcome=TerminalOutcome.COMMITTED,
            semantic_hash=current.semantic_hash,
            payload={"receipt_hash": "receipt-2"},
        ),
        _event(7, EvidenceEventType.COMMAND_APPLIED, semantic_hash=current.semantic_hash),
    )

    result = verify_evidence(current, events)

    assert result.valid is True
    assert result.highest_verified_level is EvidenceVerificationLevel.RUNTIME_AUTHORITY


def test_public_document_verifier_round_trips_and_detects_numerical_tampering() -> None:
    record = _record()
    events = (
        _event(0, EvidenceEventType.CYCLE_STARTED),
        _event(1, EvidenceEventType.CANDIDATE_PRODUCED, semantic_hash=record.semantic_hash),
        _event(
            2,
            EvidenceEventType.PLAN_COMMITTED,
            semantic_hash=record.semantic_hash,
            outcome=TerminalOutcome.COMMITTED,
            payload={"receipt_hash": "receipt-1"},
        ),
        _event(3, EvidenceEventType.COMMAND_APPLIED, semantic_hash=record.semantic_hash),
    )
    document = {
        "prediction_evidence": record.to_dict(),
        "prediction_evidence_events": [event.to_dict() for event in events],
    }

    parsed = prediction_evidence_from_dict(document["prediction_evidence"])
    valid = verify_evidence_document(document)
    tampered = json.loads(json.dumps(document))
    tampered["prediction_evidence"]["ownship"]["north_m"][1] += 1.0
    invalid = verify_evidence_document(tampered)

    assert parsed.semantic_hash == record.semantic_hash
    assert valid.valid is True
    assert valid.highest_verified_level is EvidenceVerificationLevel.RUNTIME_AUTHORITY
    assert invalid.valid is False
    assert invalid.failures == ("SEMANTIC_HASH_MISMATCH",)

    numerical_tamper = json.loads(json.dumps(document))
    numerical_tamper["prediction_evidence"]["ownship"]["north_m"][1] += 1.0
    tampered_record = prediction_evidence_from_dict(numerical_tamper["prediction_evidence"])
    numerical_tamper["prediction_evidence"]["semantic_hash"] = tampered_record.semantic_hash
    for event in numerical_tamper["prediction_evidence_events"]:
        if event["semantic_hash"] is not None:
            event["semantic_hash"] = tampered_record.semantic_hash
    numerical_invalid = verify_evidence_document(numerical_tamper)
    assert numerical_invalid.valid is False
    assert numerical_invalid.highest_verified_level is EvidenceVerificationLevel.LINEAGE
    assert numerical_invalid.failures == ("NUMERICAL_REPLAY_MISMATCH",)


def test_public_verifier_rejects_l4_verdict_that_hides_mandatory_failure() -> None:
    record = replace(
        _record(),
        acceptance={
            "accepted": True,
            "mandatory_failures": [{"code": "SAFETY_SWEPT_CLEARANCE"}],
        },
    )
    result = verify_evidence(
        record,
        (
            _event(0, EvidenceEventType.CYCLE_STARTED),
            _event(1, EvidenceEventType.PLAN_REJECTED, outcome=TerminalOutcome.REJECTED),
        ),
    )

    assert result.valid is False
    assert result.highest_verified_level is EvidenceVerificationLevel.NUMERICAL
    assert result.failures == ("L4_VERDICT_INCONSISTENT",)
