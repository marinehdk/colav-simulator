from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from colav_simulator.experiment.g3_gate import G3DisplayResult
    from colav_simulator.experiment.runner import RunResult

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root = str(PROJECT_ROOT)
sys.path[:] = [entry for entry in sys.path if entry != project_root]
sys.path.insert(0, project_root)

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


@pytest.fixture(autouse=True)
def close_plots_before_each_test():
    yield
    if plt is not None:
        plt.close("all")


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
        from colav_simulator.experiment.contracts import RunSpec  # noqa: PLC0415
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
        result = ExperimentRunner(PROJECT_ROOT).run(
            RunSpec(
                scenario_id=scenario_id,
                algorithm_id=algorithm_id,
                tracker_id=tracker_id,
                seed=0,
                terminate_on_collision_or_grounding=False,
                strict_no_fallback=True,
                solve_period_s=solve_period_s,
                algorithm_config=config,
                output_root=str(self.output_root / scenario_id / algorithm_id / tracker_id),
            )
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


@pytest.fixture(scope="session")
def p1_run_harness(tmp_path_factory: pytest.TempPathFactory) -> P1RunHarness:
    return P1RunHarness(tmp_path_factory.mktemp("p1-g3-runs"))
