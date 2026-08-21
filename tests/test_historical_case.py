from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from shapely.geometry import box

from colav_simulator.historical_ais import HistoricalAISDatasetReader, HistoricalAISSelection
from colav_simulator.historical_case import (
    HistoricalAISAlgorithmBinding,
    HistoricalAISCaseBuilder,
    HistoricalAISCaseBuildOutcome,
    HistoricalAISCaseBuildRequest,
    HistoricalAISCaseBuildStatus,
    HistoricalAISCompareBinding,
    HistoricalAISDiscoveryProfile,
    HistoricalAISEvaluationBinding,
    HistoricalAISHumanReferenceBinding,
    HistoricalAISNominalIntent,
)
from colav_simulator.historical_enc import ENCRegionProfile


def _dataset(tmp_path: Path) -> tuple[object, HistoricalAISSelection]:
    source = tmp_path / "no-encounter.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0,62.0,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.001,62.0,10,90,40,8\n"
        "2026-07-01T00:00:00Z,223456789,10.0,62.0,10,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,10.001,62.0,10,270,40,8\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    return HistoricalAISDatasetReader(source).read(selection), selection


def _buildable_dataset(tmp_path: Path) -> tuple[object, HistoricalAISSelection]:
    source = tmp_path / "buildable.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0100,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,7.0094,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:20Z,223456789,7.0088,62.0000,10,270,40,8\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    return HistoricalAISDatasetReader(source).read(selection), selection


def test_case_builder_returns_typed_no_encounter_outcome(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    dataset, selection = _dataset(tmp_path)
    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=dataset,
            selection=selection,
            enc_profile=qualified_historical_enc_profile,
            discovery_profile=HistoricalAISDiscoveryProfile(max_encounter_range_m=1_000.0),
        )
    )

    assert outcome.status is HistoricalAISCaseBuildStatus.NO_ENCOUNTER
    assert outcome.case is None
    assert outcome.success is False
    assert outcome.failure_code == HistoricalAISCaseBuildStatus.NO_ENCOUNTER.value


def test_case_builder_freezes_typed_benchmark_bindings(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    dataset, selection = _buildable_dataset(tmp_path)
    human = HistoricalAISHumanReferenceBinding(
        artifact_digest="human-reference-v1",
        sample_count=12,
    )
    algorithm = HistoricalAISAlgorithmBinding(
        algorithm_id="mid_mpc_ipopt",
        configuration_digest="algorithm-config-v1",
    )
    evaluation = HistoricalAISEvaluationBinding(
        evaluator_id="colav_evaluation_tool",
        profile_id="historical-real-window-v1",
        profile_digest="evaluator-profile-v1",
    )
    compare = HistoricalAISCompareBinding(
        contract_id="historical-benchmark-compare.v1",
        alignment_profile_digest="alignment-profile-v1",
    )

    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=dataset,
            selection=selection,
            enc_profile=qualified_historical_enc_profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(
                max_encounter_range_m=2_000.0,
                min_closing_speed_mps=0.0,
            ),
            require_intent=False,
            human_reference_binding=human,
            algorithm_binding=algorithm,
            evaluation_binding=evaluation,
            compare_binding=compare,
        )
    )

    assert outcome.success is True
    assert outcome.case is not None
    assert outcome.case.human_reference_binding is human
    assert outcome.case.algorithm_binding is algorithm
    assert outcome.case.evaluation_binding is evaluation
    assert outcome.case.compare_binding is compare
    assert outcome.case.to_dict()["human_reference_binding"]["comparison_only"] is True


def test_case_builder_discovers_head_on_crossing_overtaking_and_multi_ship(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    source = tmp_path / "encounters.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0100,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,7.0094,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:20Z,223456789,7.0088,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:00Z,323456789,7.0000,62.0060,10,180,40,8\n"
        "2026-07-01T00:00:10Z,323456789,7.0000,62.0054,10,180,40,8\n"
        "2026-07-01T00:00:20Z,323456789,7.0000,62.0048,10,180,40,8\n"
        "2026-07-01T00:00:00Z,423456789,7.0060,62.0000,8,90,40,8\n"
        "2026-07-01T00:00:10Z,423456789,7.0064,62.0000,8,90,40,8\n"
        "2026-07-01T00:00:20Z,423456789,7.0068,62.0000,8,90,40,8\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    dataset = HistoricalAISDatasetReader(source).read(selection)
    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=dataset,
            selection=selection,
            enc_profile=qualified_historical_enc_profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(
                max_encounter_range_m=2_000.0,
                min_closing_speed_mps=0.0,
            ),
            require_intent=False,
        )
    )

    assert outcome.success is True
    assert outcome.case is not None
    assert outcome.case.is_draft is True
    assert set(outcome.case.discovery.encounter_types) == {"HEAD_ON", "CROSSING", "OVERTAKING"}
    assert outcome.case.discovery.multi_ship is True
    assert all(candidate.discovery_only for candidate in outcome.case.discovery.candidates)
    assert all(candidate.concurrent_target_count == 3 for candidate in outcome.case.discovery.candidates)


def test_case_builder_fails_closed_when_selected_dimensions_are_unavailable(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    source = tmp_path / "missing-dimensions.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0100,62.0000,10,270,,\n"
        "2026-07-01T00:00:10Z,223456789,7.0094,62.0000,10,270,,\n"
        "2026-07-01T00:00:20Z,223456789,7.0088,62.0000,10,270,,\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=HistoricalAISDatasetReader(source).read(selection),
            selection=selection,
            enc_profile=qualified_historical_enc_profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(
                max_encounter_range_m=2_000.0,
                min_closing_speed_mps=0.0,
            ),
            require_intent=False,
        )
    )

    assert outcome.status is HistoricalAISCaseBuildStatus.DIMENSIONS_UNAVAILABLE
    assert outcome.details["missing_mmsi"] == (223456789,)


def test_case_builder_fails_closed_for_out_of_enc_selection(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    source = tmp_path / "out-of-enc.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0100,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,7.0094,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:20Z,223456789,7.0088,62.0000,10,270,40,8\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    dataset = HistoricalAISDatasetReader(source).read(selection)
    profile = replace(
        qualified_historical_enc_profile,
        supported_extent_projected=(0.0, 0.0, 1.0, 1.0),
        coverage_geometry_wkb=box(0.0, 0.0, 1.0, 1.0).wkb,
    )
    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=dataset,
            selection=selection,
            enc_profile=profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(max_encounter_range_m=1_000.0),
            require_intent=False,
        )
    )

    assert outcome.status is HistoricalAISCaseBuildStatus.ENC_UNQUALIFIED
    assert outcome.details["enc_preflight"]["status"] == "OUTSIDE_COVERAGE"


def test_case_builder_fits_nominal_intent_strictly_before_t0(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    source = tmp_path / "t0.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,180,40,8\n"
        "2026-07-01T00:00:30Z,123456789,7.0012,61.9994,10,180,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0100,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,7.0094,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:20Z,223456789,7.0088,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:30Z,223456789,7.0082,62.0000,10,270,40,8\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    t0 = datetime(2026, 7, 1, 0, 0, 20, tzinfo=UTC)
    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=HistoricalAISDatasetReader(source).read(selection),
            selection=selection,
            enc_profile=qualified_historical_enc_profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(
                max_encounter_range_m=2_000.0,
                min_closing_speed_mps=0.0,
            ),
            t0_utc=t0,
        )
    )

    assert outcome.success is True
    assert outcome.case is not None
    assert outcome.case.t0_candidate is not None
    assert outcome.case.t0_candidate.candidate_time_utc == t0
    assert outcome.case.nominal_intent is not None
    assert outcome.case.nominal_intent.strict_pre_t0_only is True
    assert all(timestamp < t0 for timestamp in outcome.case.nominal_intent.source_timestamps_utc)
    assert t0 not in outcome.case.nominal_intent.source_timestamps_utc
    assert outcome.case.nominal_intent.source_sample_count == 2


def test_case_builder_returns_intent_not_established_without_pre_t0_history(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    source = tmp_path / "t0-without-history.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0100,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,7.0094,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:20Z,223456789,7.0088,62.0000,10,270,40,8\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    dataset = HistoricalAISDatasetReader(source).read(selection)
    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=dataset,
            selection=selection,
            enc_profile=qualified_historical_enc_profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(
                max_encounter_range_m=1_000.0,
                min_closing_speed_mps=0.0,
            ),
            t0_utc=datetime(2026, 7, 1, tzinfo=UTC),
        )
    )

    assert outcome.status is HistoricalAISCaseBuildStatus.INTENT_NOT_ESTABLISHED


def test_case_builder_repeats_identical_lineage_and_build_digest(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    dataset, selection = _buildable_dataset(tmp_path)
    request = HistoricalAISCaseBuildRequest(
        dataset=dataset,
        selection=selection,
        enc_profile=qualified_historical_enc_profile,
        reference_mmsi=123456789,
        discovery_profile=HistoricalAISDiscoveryProfile(max_encounter_range_m=2_000.0, min_closing_speed_mps=0.0),
        require_intent=False,
    )
    first = HistoricalAISCaseBuilder().build(request)
    second = HistoricalAISCaseBuilder().build(request)

    assert first.success is True
    assert second.success is True
    assert first.case is not None and second.case is not None
    assert first.case.build_digest == second.case.build_digest
    assert first.case.discovery.discovery_digest == second.case.discovery.discovery_digest
    assert first.to_dict() == second.to_dict()


def test_case_builder_requires_dataset_selection_lineage(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    dataset, _selection = _buildable_dataset(tmp_path)

    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=dataset,
            enc_profile=qualified_historical_enc_profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(
                max_encounter_range_m=2_000.0,
                min_closing_speed_mps=0.0,
            ),
            require_intent=False,
        )
    )

    assert outcome.status is HistoricalAISCaseBuildStatus.INVALID_REQUEST
    assert "selection" in outcome.message.lower()


def test_nominal_intent_rejects_non_finite_or_negative_fit_values() -> None:
    with pytest.raises(ValueError, match="intent fit values"):
        HistoricalAISNominalIntent(
            reference_mmsi=123456789,
            t0_utc=datetime(2026, 7, 1, tzinfo=UTC),
            t0_s=0.0,
            course_rad=0.0,
            speed_mps=-1.0,
            fit_error_m=0.0,
            source_sample_count=1,
            source_timestamps_utc=(datetime(2026, 6, 30, tzinfo=UTC),),
            source_observation_refs=(),
            route_points_vxvy=((0.0, 0.0), (1.0, 0.0)),
        )


def test_case_request_rejects_conflicting_reference_vessel_aliases(tmp_path: Path) -> None:
    dataset, selection = _buildable_dataset(tmp_path)

    with pytest.raises(ValueError, match="disagree"):
        HistoricalAISCaseBuildRequest(
            dataset=dataset,
            selection=selection,
            reference_mmsi=123456789,
            reference_vessel_mmsi=223456789,
        )


def test_case_builder_rejects_t0_without_post_t0_coverage(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    dataset, selection = _buildable_dataset(tmp_path)
    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=dataset,
            selection=selection,
            enc_profile=qualified_historical_enc_profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(
                max_encounter_range_m=2_000.0,
                min_closing_speed_mps=0.0,
            ),
            t0_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
        )
    )

    assert outcome.status is HistoricalAISCaseBuildStatus.INTENT_NOT_ESTABLISHED


def test_case_builder_rejects_initially_overlapping_selected_vessels(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    source = tmp_path / "initial-overlap.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0000,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,7.0000,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:20Z,223456789,7.0000,62.0000,10,270,40,8\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=HistoricalAISDatasetReader(source).read(selection),
            selection=selection,
            enc_profile=qualified_historical_enc_profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(
                max_encounter_range_m=2_000.0,
                min_closing_speed_mps=0.0,
                min_initial_separation_m=10.0,
            ),
            require_intent=False,
        )
    )

    assert outcome.status is HistoricalAISCaseBuildStatus.INITIAL_SEPARATION_INVALID


def test_case_builder_reports_insufficient_common_time_coverage(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    source = tmp_path / "short-coverage.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:02Z,123456789,7.0001,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0100,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:02Z,223456789,7.0099,62.0000,10,270,40,8\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )
    outcome = HistoricalAISCaseBuilder().build(
        HistoricalAISCaseBuildRequest(
            dataset=HistoricalAISDatasetReader(source).read(selection),
            selection=selection,
            enc_profile=qualified_historical_enc_profile,
            reference_mmsi=123456789,
            discovery_profile=HistoricalAISDiscoveryProfile(
                max_encounter_range_m=2_000.0,
                min_closing_speed_mps=0.0,
                min_duration_s=10.0,
            ),
            require_intent=False,
        )
    )

    assert outcome.status is HistoricalAISCaseBuildStatus.TIME_COVERAGE_INSUFFICIENT


def test_case_builder_intent_digest_ignores_post_t0_human_reference_changes(
    tmp_path: Path, qualified_historical_enc_profile: ENCRegionProfile
) -> None:
    header = "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground,length,width\n"
    prefix = (
        "2026-07-01T00:00:00Z,123456789,7.0000,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:10Z,123456789,7.0006,62.0000,10,90,40,8\n"
        "2026-07-01T00:00:20Z,123456789,7.0012,62.0000,10,180,40,8\n"
        "2026-07-01T00:00:00Z,223456789,7.0100,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:10Z,223456789,7.0094,62.0000,10,270,40,8\n"
        "2026-07-01T00:00:20Z,223456789,7.0088,62.0000,10,270,40,8\n"
    )
    first_source = tmp_path / "a" / "human.csv"
    second_source = tmp_path / "b" / "human.csv"
    first_source.parent.mkdir()
    second_source.parent.mkdir()
    first_source.write_text(
        header + prefix + "2026-07-01T00:00:30Z,123456789,7.0012,61.9994,10,180,40,8\n"
        "2026-07-01T00:00:30Z,223456789,7.0082,62.0000,10,270,40,8\n",
        encoding="utf-8",
    )
    second_source.write_text(
        header + prefix + "2026-07-01T00:00:30Z,123456789,7.0030,62.0020,10,0,40,8\n"
        "2026-07-01T00:00:30Z,223456789,7.0082,62.0000,10,270,40,8\n",
        encoding="utf-8",
    )
    selection = HistoricalAISSelection(
        start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        end_utc=datetime(2026, 7, 1, 0, 1, tzinfo=UTC),
    )

    def build(source: Path) -> HistoricalAISCaseBuildOutcome:
        return HistoricalAISCaseBuilder().build(
            HistoricalAISCaseBuildRequest(
                dataset=HistoricalAISDatasetReader(source).read(selection),
                selection=selection,
                enc_profile=qualified_historical_enc_profile,
                reference_mmsi=123456789,
                discovery_profile=HistoricalAISDiscoveryProfile(
                    max_encounter_range_m=2_000.0,
                    min_closing_speed_mps=0.0,
                ),
                t0_utc=datetime(2026, 7, 1, 0, 0, 20, tzinfo=UTC),
            )
        )

    first = build(first_source)
    second = build(second_source)
    assert first.success is True and second.success is True
    assert first.case is not None and second.case is not None
    assert first.case.nominal_intent is not None and second.case.nominal_intent is not None
    assert first.case.nominal_intent.intent_digest == second.case.nominal_intent.intent_digest
    assert first.case.runtime_digest == second.case.runtime_digest
    assert first.case.case_digest == second.case.case_digest
    assert first.case.build_digest != second.case.build_digest
