from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from shapely.geometry import box

from colav_simulator.historical_ais import (
    HistoricalAISDatasetDescriptor,
    HistoricalAISDatasetReader,
    HistoricalAISReadResult,
)
from colav_simulator.historical_enc import (
    ENCCacheIdentity,
    ENCLayerIdentity,
    ENCPreflightRequest,
    ENCPreflightStatus,
    ENCQualificationState,
    ENCRegionProfile,
    ENCSimulationProjection,
    ENCSourceIdentity,
    build_expanded_romsdal_profile,
    build_small_romsdal_profile,
)


def _profile(
    *,
    qualification_state: ENCQualificationState = ENCQualificationState.QUALIFIED,
    input_crs: str = "EPSG:4326",
    cache_source_digest: str = "source-digest",
) -> ENCRegionProfile:
    return ENCRegionProfile(
        profile_id="romsdal-expanded-test",
        profile_version="1.0.0",
        source=ENCSourceIdentity(
            provider="Kartverket",
            source_name="More_og_Romsdal_utm33.gdb",
            source_digest="source-digest",
            source_crs="EPSG:25833",
            format="FileGDB",
        ),
        projection=ENCSimulationProjection(
            input_crs=input_crs,
            simulation_crs="EPSG:25833",
            utm_zone=33,
        ),
        supported_extent_wgs84=(6.0, 62.4, 6.5, 62.8),
        supported_extent_projected=(30000.0, 6950000.0, 70000.0, 7000000.0),
        hazard_layers=(ENCLayerIdentity("LAND", "landareal", 1),),
        navigability_layers=(ENCLayerIdentity("DEPARE", "dybdeareal", 1),),
        cache=ENCCacheIdentity(
            cache_id="cache-1",
            preprocessing_version="enc-preprocess.v1",
            source_digest=cache_source_digest,
            artifact_digest="cache-digest",
        ),
        qualification_state=qualification_state,
        qualification_reasons=(),
        provenance={"qualification": "deterministic-test-fixture"},
        coverage_geometry_wkb=box(30000.0, 6950000.0, 70000.0, 7000000.0).wkb,
        hazard_geometry_wkb=box(50000.0, 6960000.0, 51000.0, 6970000.0).wkb,
    )


def test_qualified_profile_projects_wgs84_and_round_trips_within_tolerance() -> None:
    profile = _profile()
    request = ENCPreflightRequest(
        positions=(
            ("ownship", 6.05, 62.45),
            ("target-1", 6.10, 62.50),
        ),
        input_crs="EPSG:4326",
    )

    result = profile.preflight(request)

    assert result.status is ENCPreflightStatus.PASS
    assert result.all_positions_contained is True
    projected = profile.projection.project_wgs84((6.05, 62.45))
    round_trip = profile.projection.to_wgs84(projected)
    assert round_trip[0] == pytest.approx(6.05, abs=1e-7)
    assert round_trip[1] == pytest.approx(62.45, abs=1e-7)
    assert result.checked_observation_ids == ("ownship", "target-1")


def test_outside_position_fails_closed_with_typed_coverage_result() -> None:
    result = _profile().preflight(ENCPreflightRequest(positions=(("outside", 7.0, 62.45),), input_crs="EPSG:4326"))

    assert result.status is ENCPreflightStatus.OUTSIDE_COVERAGE
    assert result.all_positions_contained is False
    assert result.outside_observation_ids == ("outside",)
    assert result.failure_codes == ("OUTSIDE_COVERAGE",)


def test_unqualified_profile_cannot_authorize_a_contained_subset() -> None:
    result = _profile(qualification_state=ENCQualificationState.INCOMPLETE).preflight(
        ENCPreflightRequest(positions=(("inside", 6.05, 62.45),), input_crs="EPSG:4326")
    )

    assert result.status is ENCPreflightStatus.UNQUALIFIED
    assert result.all_positions_contained is True
    assert result.failure_codes == ("PROFILE_INCOMPLETE",)


def test_wrong_input_crs_fails_before_projection() -> None:
    result = _profile().preflight(ENCPreflightRequest(positions=(("wrong-crs", 6.05, 62.45),), input_crs="EPSG:32632"))

    assert result.status is ENCPreflightStatus.CRS_MISMATCH
    assert result.failure_codes == ("CRS_MISMATCH",)


def test_empty_selected_subset_is_invalid_for_case_preflight() -> None:
    result = _profile().preflight(ENCPreflightRequest(positions=(), input_crs="EPSG:4326"))

    assert result.status is ENCPreflightStatus.INVALID_REQUEST
    assert result.failure_codes == ("EMPTY_SELECTION",)


def test_hazard_intersection_is_not_reported_as_chart_qualification() -> None:
    projected_hazard = (50500.0, 6965000.0)
    lon, lat = _profile().projection.to_wgs84(projected_hazard)

    result = _profile().preflight(ENCPreflightRequest(positions=(("hazard", lon, lat),), input_crs="EPSG:4326"))

    assert result.status is ENCPreflightStatus.UNQUALIFIED
    assert result.hazard_observation_ids == ("hazard",)
    assert result.failure_codes == ("HAZARD_INTERSECTION",)


def test_route_segment_intersection_is_typed_even_when_endpoints_are_clear() -> None:
    projection = _profile().projection
    route = (
        projection.to_wgs84((49000.0, 6965000.0)),
        projection.to_wgs84((52000.0, 6965000.0)),
    )

    result = _profile().preflight(
        ENCPreflightRequest(
            positions=(("route-start", route[0][0], route[0][1]), ("route-end", route[1][0], route[1][1])),
            input_crs="EPSG:4326",
            route_points=route,
        )
    )

    assert result.status is ENCPreflightStatus.UNQUALIFIED
    assert result.hazard_observation_ids == ()
    assert result.failure_codes == ("ROUTE_HAZARD_INTERSECTION",)


def test_route_outside_supported_extent_fails_closed() -> None:
    projection = _profile().projection
    route = (
        projection.to_wgs84((25000.0, 6965000.0)),
        projection.to_wgs84((45000.0, 6965000.0)),
    )

    result = _profile().preflight(
        ENCPreflightRequest(
            positions=(("route-start", 6.05, 62.45),),
            input_crs="EPSG:4326",
            route_points=route,
        )
    )

    assert result.status is ENCPreflightStatus.OUTSIDE_COVERAGE
    assert result.failure_codes == ("ROUTE_OUTSIDE_COVERAGE",)


def test_navigability_cache_rejects_non_navigable_point_inside_chart_extent() -> None:
    profile = replace(
        _profile(),
        navigability_geometry_wkb=box(30000.0, 6950000.0, 49000.0, 7000000.0).wkb,
    )
    longitude, latitude = profile.projection.to_wgs84((60000.0, 6970000.0))

    result = profile.preflight(
        ENCPreflightRequest(positions=(("non-navigable", longitude, latitude),), input_crs="EPSG:4326")
    )

    assert result.status is ENCPreflightStatus.UNQUALIFIED
    assert result.navigability_observation_ids == ("non-navigable",)
    assert result.failure_codes == ("NAVIGABILITY_UNKNOWN",)


def test_profile_and_cache_are_immutable_and_digest_is_versioned() -> None:
    profile = _profile()

    assert profile.profile_digest
    assert profile.to_dict()["profile_version"] == "1.0.0"
    with pytest.raises(FrozenInstanceError):
        profile.profile_id = "other"  # type: ignore[misc]


def test_profile_digest_is_not_tied_to_local_source_path() -> None:
    first = _profile()
    second = replace(
        first,
        provenance={"qualification": "deterministic-test-fixture", "source_path": "/other/checkout"},
    )

    assert first.profile_digest == second.profile_digest
    assert second.to_dict()["provenance"]["source_path"] == "/other/checkout"


def test_stale_cache_cannot_pass_even_when_profile_is_marked_qualified() -> None:
    result = _profile(cache_source_digest="different-source").preflight(
        ENCPreflightRequest(positions=(("inside", 6.05, 62.45),), input_crs="EPSG:4326")
    )

    assert result.status is ENCPreflightStatus.UNQUALIFIED
    assert result.failure_codes == ("STALE_CACHE",)


def test_source_and_simulation_crs_mismatch_invalidates_qualified_profile() -> None:
    profile = _profile()
    source = ENCSourceIdentity(
        provider=profile.source.provider,
        source_name=profile.source.source_name,
        source_digest=profile.source.source_digest,
        source_crs="EPSG:32632",
        format=profile.source.format,
    )
    mismatched = ENCRegionProfile(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        source=source,
        projection=profile.projection,
        supported_extent_wgs84=profile.supported_extent_wgs84,
        supported_extent_projected=profile.supported_extent_projected,
        hazard_layers=profile.hazard_layers,
        navigability_layers=profile.navigability_layers,
        cache=profile.cache,
        qualification_state=profile.qualification_state,
        qualification_reasons=profile.qualification_reasons,
        provenance=profile.provenance,
        coverage_geometry_wkb=profile.coverage_geometry_wkb,
        hazard_geometry_wkb=profile.hazard_geometry_wkb,
    )

    result = mismatched.preflight(ENCPreflightRequest(positions=(("inside", 6.05, 62.45),), input_crs="EPSG:4326"))

    assert result.status is ENCPreflightStatus.UNQUALIFIED
    assert result.failure_codes == ("SOURCE_CRS_MISMATCH",)


def test_historical_ais_read_result_is_consumable_at_enc_preflight_seam(tmp_path: Path) -> None:
    source = tmp_path / "selected.csv"
    source.write_text(
        "date_time_utc,mmsi,longitude,latitude,speed_over_ground,course_over_ground\n"
        "2026-07-01T00:00:00Z,123456789,6.05,62.45,5,90\n",
        encoding="utf-8",
    )

    read_result = HistoricalAISDatasetReader(source).read()
    result = _profile().preflight_historical_ais(read_result)

    assert result.status is ENCPreflightStatus.PASS
    assert result.checked_observation_ids == ("selected.csv:0",)


def test_empty_historical_read_result_returns_typed_invalid_preflight() -> None:
    descriptor = HistoricalAISDatasetDescriptor(
        provider="Kystverket",
        format="csv",
        entries=(),
        archive_sha256="archive",
        entry_digests=(),
        schema_sha256="schema",
        selection_sha256="selection",
        normalized_sha256="normalized",
        row_count=0,
        normalized_row_count=0,
        schema_fields=(),
        quality_findings=(),
        source_row_count=0,
    )

    result = _profile().preflight_historical_ais(HistoricalAISReadResult(descriptor, ()))

    assert result.status is ENCPreflightStatus.INVALID_REQUEST
    assert result.failure_codes == ("EMPTY_SELECTION",)


def test_expanded_romsdal_factory_binds_real_source_and_cache_identity() -> None:
    source = Path("data/enc/More_og_Romsdal_utm33.gdb")
    if not source.is_dir():
        pytest.skip("local ENC source is not installed in this checkout")

    profile = build_expanded_romsdal_profile(source)

    assert profile.qualification_state is ENCQualificationState.QUALIFIED
    assert profile.source.source_crs == "EPSG:25833"
    assert profile.source.source_digest != "UNAVAILABLE"
    assert profile.cache.source_digest == profile.source.source_digest
    assert {item.source_layer for item in profile.hazard_layers} >= {"landareal", "torrfall", "skjer"}
    assert profile.navigability_layers[0].source_layer == "dybdeareal"
    assert profile.cache.artifact_digest != "UNAVAILABLE"


def test_missing_enc_source_returns_typed_incomplete_profile() -> None:
    profile = build_expanded_romsdal_profile(Path("/tmp/does-not-exist-romsdal.gdb"))

    assert profile.qualification_state is ENCQualificationState.INCOMPLETE
    assert "SOURCE_MISSING" in profile.qualification_reasons
    result = profile.preflight(ENCPreflightRequest(positions=(("inside", 6.05, 62.45),), input_crs="EPSG:4326"))
    assert result.status is ENCPreflightStatus.UNQUALIFIED
    assert "PROFILE_INCOMPLETE" in result.failure_codes


def test_small_romsdal_fixture_has_a_distinct_versioned_profile() -> None:
    source = Path("data/enc/More_og_Romsdal_utm33.gdb")
    if not source.is_dir():
        pytest.skip("local ENC source is not installed in this checkout")

    profile = build_small_romsdal_profile(source)

    assert profile.profile_id == "romsdal-small"
    assert profile.profile_version == "1.0.0"
    assert profile.supported_extent_projected == (38500.0, 6955450.0, 43500.0, 6960450.0)
    assert profile.cache.cache_id.startswith("romsdal-small-")
