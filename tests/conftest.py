from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

os.environ["MPLBACKEND"] = "Agg"

if TYPE_CHECKING:
    from colav_simulator.experiment.g3_gate import G3DisplayResult
    from colav_simulator.experiment.runner import RunResult
    from colav_simulator.historical_enc import ENCRegionProfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root = str(PROJECT_ROOT)
sys.path[:] = [entry for entry in sys.path if entry != project_root]
sys.path.insert(0, project_root)

try:
    import matplotlib as mpl

    mpl.use("Agg", force=True)
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


@pytest.fixture(autouse=True)
def close_plots_before_each_test(monkeypatch: pytest.MonkeyPatch):
    if plt is not None:
        monkeypatch.setattr(plt, "show", lambda *args, **kwargs: None)
    yield
    if plt is not None:
        plt.close("all")


@pytest.fixture
def qualified_historical_enc_profile() -> ENCRegionProfile:
    """Public-contract ENC profile shared by historical seam tests."""
    from shapely.geometry import box  # noqa: PLC0415

    from colav_simulator.historical_enc import (  # noqa: PLC0415
        ENCCacheIdentity,
        ENCLayerIdentity,
        ENCQualificationState,
        ENCRegionProfile,
        ENCSimulationProjection,
        ENCSourceIdentity,
    )

    return ENCRegionProfile(
        profile_id="case-test",
        profile_version="1.0.0",
        source=ENCSourceIdentity(
            provider="test",
            source_name="test.gdb",
            source_digest="source-digest",
            source_crs="EPSG:25833",
            format="FileGDB",
        ),
        projection=ENCSimulationProjection(
            input_crs="EPSG:4326",
            simulation_crs="EPSG:25833",
            utm_zone=33,
        ),
        supported_extent_wgs84=(0.0, 50.0, 20.0, 70.0),
        supported_extent_projected=(0.0, 5_000_000.0, 1_000_000.0, 8_000_000.0),
        hazard_layers=(ENCLayerIdentity("LAND", "land", 0),),
        navigability_layers=(ENCLayerIdentity("DEPARE", "depth", 0),),
        cache=ENCCacheIdentity(
            cache_id="cache",
            preprocessing_version="test.v1",
            source_digest="source-digest",
            artifact_digest="artifact-digest",
        ),
        qualification_state=ENCQualificationState.QUALIFIED,
        qualification_reasons=(),
        provenance={"source": "test"},
        coverage_geometry_wkb=box(0.0, 5_000_000.0, 1_000_000.0, 8_000_000.0).wkb,
    )


@dataclass
class P1RunHarness:
    output_root: Path
    _nominal: dict[tuple[str, str], RunResult] = field(default_factory=dict)
    _candidate: dict[tuple[str, str, str, str, float | None], RunResult] = field(default_factory=dict)

    def run(
        self,
        scenario_id: str,
        algorithm_id: str,
        tracker_id: str = "god",
        *,
        algorithm_config: dict | None = None,
        solve_period_s: float | None = None,
    ) -> RunResult:
        from colav_simulator.experiment.contracts import (  # noqa: PLC0415
            InternalExecutionPurpose,
            RunSpec,
        )
        from colav_simulator.experiment.runner import ExperimentRunner  # noqa: PLC0415

        config = algorithm_config or {}
        key = (
            scenario_id,
            algorithm_id,
            tracker_id,
            json.dumps(config, sort_keys=True, default=str),
            solve_period_s,
        )
        if key in self._candidate:
            return self._candidate[key]
        spec = RunSpec(
            scenario_id=scenario_id,
            validation_rule_id=_validation_rule_for_scenario(scenario_id),
            algorithm_id=algorithm_id,
            tracker_id=tracker_id,
            seed=0,
            terminate_on_collision_or_grounding=False,
            strict_no_fallback=True,
            solve_period_s=solve_period_s,
            algorithm_config=config,
            output_root=str(self.output_root / scenario_id / algorithm_id / tracker_id),
        )
        runner = ExperimentRunner(PROJECT_ROOT)
        result = (
            runner.run_internal(spec, purpose=InternalExecutionPurpose.EVALUATOR_BASELINE)
            if algorithm_id == "nominal"
            else runner.run(spec)
        )
        self._candidate[key] = result
        return result

    def compare(
        self,
        scenario_id: str,
        algorithm_id: str,
        tracker_id: str = "god",
        *,
        algorithm_config: dict | None = None,
        solve_period_s: float | None = None,
    ) -> G3DisplayResult:
        from colav_simulator.experiment.g3_gate import evaluate_g3_display  # noqa: PLC0415

        key = (scenario_id, tracker_id)
        if key not in self._nominal:
            self._nominal[key] = self.run(scenario_id, "nominal", tracker_id)
        nominal = self._nominal[key]
        candidate = self.run(
            scenario_id,
            algorithm_id,
            tracker_id,
            algorithm_config=algorithm_config,
            solve_period_s=solve_period_s,
        )
        return evaluate_g3_display(
            nominal_frames=nominal.session.frames,
            candidate_frames=candidate.session.frames,
            nominal_events=nominal.session.events,
            candidate_events=candidate.session.events,
            nominal_manifest=nominal.manifest,
            candidate_manifest=candidate.manifest,
            ship_info=candidate.session.ship_info,
            expected_algorithm=algorithm_id,
            dt_sim=candidate.session.config.dt_sim,
        )


def _validation_rule_for_scenario(scenario_id: str) -> str:
    """Map a published P1 scenario to its exact product validation rule."""
    if scenario_id in {"overtaking", "overtaken"}:
        return "rule13"
    if scenario_id == "head_on":
        return "rule14"
    if scenario_id in {"crossing_give_way", "crossing_stand_on"}:
        return "rule15"
    if scenario_id in {"paper_ccta2023_multiship", "romsdal_busy_water_16"}:
        return "multiship"
    raise ValueError(f"P1 harness has no product validation rule for {scenario_id!r}")


@pytest.fixture(scope="session")
def p1_run_harness(tmp_path_factory: pytest.TempPathFactory) -> P1RunHarness:
    return P1RunHarness(tmp_path_factory.mktemp("p1-g3-runs"))
