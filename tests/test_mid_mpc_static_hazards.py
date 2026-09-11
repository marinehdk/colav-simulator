"""ENC hazards must constrain the executable prediction, including between knots."""

import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import casadi as ca
import fiona
import numpy as np
import pytest
from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box

from colav_simulator.common.enc_point_hazards import chart_point_hazards
from colav_simulator.core.colav.custom_mpc_adapter import FactoryContext, PlannerInput
from colav_simulator.core.colav.diagnostics import ColavExecutionError
from colav_simulator.core.colav.mid_mpc import MidMpcConfig, MidMpcOwnShip, MidMpcProblem, MidMpcRouteFrame
from colav_simulator.core.colav.mid_mpc.solver import _P, _colreg_cost, _pack_parameters, _static_rows
from colav_simulator.core.colav.mid_mpc_acceptance import MidMpcPlanAcceptance, _static_geometry_clearance
from colav_simulator.core.colav.mid_mpc_static import compile_static_field, static_execution_context, static_hazards
from colav_simulator.core.colav.threat_management import ThreatManagementCoordinator
from colav_simulator.integrations.mid_mpc_ipopt import (
    _SOLVER_RESERVATION_FLOOR_S,
    _MidMpcFacade,
    create,
)


def _enc(hazard, layer="land") -> SimpleNamespace:
    empty = SimpleNamespace(geometry=GeometryCollection())
    water = SimpleNamespace(geometry=box(-10000, -10000, 10000, 10000))
    layers = {"land": empty, "shore": empty, "seabed": {0: water, 5: water}}
    layers[layer] = SimpleNamespace(geometry=hazard)
    return SimpleNamespace(**layers)


def _input(enc) -> PlannerInput:
    return PlannerInput(
        sim_time_s=0.0,
        dt_sim_s=0.1,
        waypoints_enu_m=np.array([[0.0, 10000.0], [0.0, 0.0]]),
        speed_plan_mps=np.array([6.0, 6.0]),
        ownship_state=np.array([0.0, 0.0, 0.0, 6.0, 0.0, 0.0]),
        tracks=(),
        enc=enc,
        goal_state=None,
        disturbance=None,
        algorithm_seed=0,
        ownship_model="KinematicCSOG",
        ownship_controller="PassThroughCS",
    )


def _facade() -> _MidMpcFacade:
    return create(
        context=FactoryContext(
            requested_algorithm="mid_mpc_ipopt",
            algorithm_seed=0,
            scenario_id="static-hazards",
            tracker_id="god",
            threat_management_coordinator=ThreatManagementCoordinator(),
        )
    )._solve.__self__


@pytest.mark.parametrize("layer", ["land", "uwtroc", "obstrn"])
def test_real_ipopt_prediction_goes_around_island(layer: str) -> None:
    island = box(-40, 500, 40, 650)
    data = _input(_enc(island, layer))
    solution = _facade().solve(data)
    assert solution.feasible
    path = LineString(solution.predicted_trajectory[[1, 0]].T)
    radius = 0.5 * np.hypot(data.ownship_length_m, data.ownship_width_m)
    assert path.distance(island) > radius
    assert solution.predicted_trajectory[0, -1] > 1000


def test_l4_rejects_between_knot_reef_even_with_fake_safe_scalar() -> None:
    data = _input(_enc(box(-1, 14, 1, 16), "uwtroc"))
    request = SimpleNamespace(
        candidate=SimpleNamespace(north_m=np.array([0.0, 30.0]), east_m=np.zeros(2)),
        execution=SimpleNamespace(
            ownship_length_m=15.0,
            ownship_width_m=4.0,
            targets=(),
            static_clearance_m=1e6,
            **static_execution_context(data),
        ),
        authority=SimpleNamespace(targets=()),
        policy=SimpleNamespace(hard_static_clearance_m=1.0),
    )
    findings = []
    MidMpcPlanAcceptance._safety(request, findings)
    assert "SAFETY_STATIC_CLEARANCE" in {f.code for f in findings}
    assert _static_geometry_clearance(request) < 0


def test_current_position_is_included_in_held_static_check() -> None:
    data = _input(_enc(box(-2, 10, 2, 12)))
    request = SimpleNamespace(
        candidate=SimpleNamespace(north_m=np.array([30.0, 60.0]), east_m=np.zeros(2)),
        execution=SimpleNamespace(ownship_length_m=15.0, ownship_width_m=4.0, **static_execution_context(data)),
    )
    assert _static_geometry_clearance(request) < 0


def test_shallow_depth_and_missing_reef_sources_are_explicit() -> None:
    enc = _enc(GeometryCollection())
    shallow = box(-20, 250, 20, 300)
    enc.seabed[5] = SimpleNamespace(geometry=enc.seabed[0].geometry.difference(shallow))
    hazards = static_hazards(_input(enc))
    assert hazards.combined_geometry.equals(shallow)
    statuses = {layer.layer_id: layer.source_status for layer in hazards.layers}
    assert statuses["UWTROC"] == "UNAVAILABLE_SOURCE"
    enc.seabed = {0: enc.seabed[0]}
    with pytest.raises(ValueError, match="no depth bin"):
        static_hazards(_input(enc))


def test_mixed_point_reef_and_land_with_hole_have_conservative_grid() -> None:
    island = Polygon(box(-100, -100, 100, 100).exterior.coords, [box(-50, -50, 50, 50).exterior.coords])
    enc = _enc(island)
    enc.uwtroc = SimpleNamespace(geometry=Point(160, 160))
    data = _input(enc)
    field = compile_static_field(data)
    assert field is not None
    nn = field.north_min_m + np.arange(field.north_count) * field.spacing_m
    ee = field.east_min_m + np.arange(field.east_count) * field.spacing_m
    lookup = ca.interpolant("test_static_distance", "linear", [nn, ee], field.distance_m)
    assert float(lookup([0.0, 0.0])) > 0  # A navigable hole stays water.
    assert float(lookup([0.0, 80.0])) < 0
    assert float(lookup([160.0, 160.0])) == 0
    samples = np.random.default_rng(4).uniform([nn[0], ee[0]], [nn[-1], ee[-1]], (100, 2))
    geometry = static_hazards(data).combined_geometry
    for north, east in samples:
        point = Point(east, north)
        exact = point.distance(geometry)
        if island.contains(point):
            exact = -point.distance(island.boundary)
        lower = float(lookup([north, east])) - field.spacing_m / np.sqrt(2.0)
        assert lower <= exact + 1e-9


def test_absolute_grid_and_changed_chart_invalidate_cache() -> None:
    data = _input(_enc(box(-40, 500, 40, 650)))
    field = compile_static_field(data)
    moved = replace(data, ownship_state=data.ownship_state + np.array([10, 20, 0, 0, 0, 0]))
    assert compile_static_field(moved) is field
    data.enc.land = SimpleNamespace(geometry=box(-40, 550, 40, 650))
    changed = compile_static_field(data)
    assert changed.source_hash != field.source_hash
    assert changed.graph_key != field.graph_key


def test_raw_chart_reef_layers_filter_depth_and_preserve_skerries(tmp_path: Path) -> None:
    source = tmp_path / "reefs.gpkg"
    for layer in ("grunne", "skjer"):
        with fiona.open(
            source,
            "w",
            driver="GPKG",
            layer=layer,
            crs="EPSG:25833",
            schema={"geometry": "Point", "properties": {"dybde": "float"}},
        ) as sink:
            for east, depth in [(50.0, 1.0), (60.0, 20.0), (70.0, None)]:
                sink.write({"geometry": {"type": "Point", "coordinates": (east, 80.0)}, "properties": {"dybde": depth}})
    enc = _enc(GeometryCollection())
    enc._environment = SimpleNamespace(scope=SimpleNamespace(files=[str(source)]))
    enc.bbox = (0, 0, 100, 100)
    enc.utm_zone = 33
    reefs = chart_point_hazards(enc, 2.0)
    assert reefs["UWTROC"][0].covers(Point(50, 80))
    assert reefs["UWTROC"][0].covers(Point(70, 80))
    assert not reefs["UWTROC"][0].covers(Point(60, 80))
    assert reefs["SKJER"][0].covers(Point(60, 80))
    assert chart_point_hazards(enc, 25.0)["UWTROC"][0].covers(Point(60, 80))
    layers = {layer.layer_id: layer for layer in static_hazards(_input(enc)).layers}
    assert layers["UWTROC"].source_status == "KARTVERKET_GRUNNE_DEPTH_FILTERED"
    assert layers["SKJER"].source_status == "KARTVERKET_SKJER"


def test_product_chart_contains_real_underwater_and_exposed_reefs() -> None:
    source = Path(__file__).resolve().parents[1] / "data/enc/More_og_Romsdal_utm33.gdb"
    if not source.exists():
        pytest.skip("local Kartverket dataset is not installed")
    enc = _enc(GeometryCollection())
    enc._environment = SimpleNamespace(scope=SimpleNamespace(files=[str(source)]))
    enc.bbox = (38500.0, 6955450.0, 43500.0, 6960450.0)
    enc.utm_zone = 33
    reefs = chart_point_hazards(enc, 2.0)
    assert len(reefs["UWTROC"][0].geoms) == 56
    assert len(reefs["SKJER"][0].geoms) == 2


def test_adapter_requires_enc_before_dispatch() -> None:
    adapter = create(context=FactoryContext("mid_mpc_ipopt", 0))
    data = _input(None)
    with pytest.raises(ColavExecutionError, match="requires ENC"):
        adapter.plan(0.0, data.waypoints_enu_m, data.speed_plan_mps, data.ownship_state, [], dt=0.1)


def test_blocked_passage_cannot_be_relaxed_or_return_a_fallback() -> None:
    adapter = create(context=FactoryContext("mid_mpc_ipopt", 0), horizon_steps=8, speed_min_mps=6.0)
    data = _input(_enc(box(-10000, 100, 10000, 150)))
    with pytest.raises(ColavExecutionError) as error:
        adapter._solve.__self__.solve(data)
    assert error.value.details["failure_code"] == "OPTIMIZER_UNRESOLVED"


def test_static_graph_preserves_full_slot_cost_and_gradient() -> None:
    config = MidMpcConfig(horizon_steps=4)
    target_start = int(_P.PREFIX_PSI) + 2 * 18
    parameters = np.zeros(target_start + 16 * 5)
    parameters[_P.CPA_SAFE] = 150.0
    for index in range(3):
        base = target_start + 5 * index
        parameters[base : base + 5] = [100 + 40 * index, 20 * index, 0.2, 4.0, 0.6]
    x = ca.MX.sym("x", 8)
    p = ca.MX.sym("p", len(parameters))
    full = _colreg_cost(x[:4], x[4:], p, config)
    compact = _colreg_cost(x[:4], x[4:], p, config, target_capacity=3)
    compare = ca.Function("compare_cost", [x, p], [full, compact, ca.gradient(full, x), ca.gradient(compact, x)])
    cost, compact_cost, gradient, compact_gradient = compare(np.r_[np.linspace(0.0, 0.3, 4), [6.0] * 4], parameters)
    assert float(compact_cost) == pytest.approx(float(cost), abs=1e-14)
    np.testing.assert_allclose(compact_gradient, gradient, rtol=0, atol=1e-14)


def test_retry_budget_includes_preparation_and_reserves_l4_time(monkeypatch) -> None:
    facade = _facade()
    facade._unresolved_streak = 1
    original_assemble = facade._assembler.assemble
    original_solve = facade._solver.solve
    observed = []

    def delayed_assembly(*args, **kwargs) -> object:
        time.sleep(0.05)
        return original_assemble(*args, **kwargs)

    def record_budget(*args, **kwargs) -> object:
        observed.append(kwargs["wall_time_s"])
        return original_solve(*args, **kwargs)

    monkeypatch.setattr(facade._assembler, "assemble", delayed_assembly)
    monkeypatch.setattr(facade._solver, "solve", record_budget)
    assert facade.solve(_input(None)).feasible
    assert 0.0 < observed[0] <= 2.0 - 0.05 - facade._config.acceptance_reservation_s


def test_retry_reserves_solver_floor_when_upstream_overruns_downgraded_budget(monkeypatch) -> None:
    """R8: a streak-downgraded cycle must not starve IPOPT below its measured need.

    Late-mission upstream work alone (measured ~4.9 s in the p4 HO cells) exceeds
    the whole 2 s downgraded budget; the solver slice must be floored so a retry
    can actually clear the streak instead of locking into starvation.
    """
    facade = _facade()
    facade._unresolved_streak = 1
    original_assemble = facade._assembler.assemble
    original_solve = facade._solver.solve
    observed = []

    def late_mission_upstream(*args, **kwargs) -> object:
        time.sleep(1.9)
        return original_assemble(*args, **kwargs)

    def record_budget(*args, **kwargs) -> object:
        observed.append(kwargs["wall_time_s"])
        return original_solve(*args, **kwargs)

    monkeypatch.setattr(facade._assembler, "assemble", late_mission_upstream)
    monkeypatch.setattr(facade._solver, "solve", record_budget)
    assert facade.solve(_input(None)).feasible
    assert observed[0] >= _SOLVER_RESERVATION_FLOOR_S
    # The downgraded cycle still bounds the solver allocation from above.
    assert observed[0] <= 2.0 - facade._config.acceptance_reservation_s


def test_solver_floor_never_extends_healthy_cycles(monkeypatch) -> None:
    """Full-budget (streak reset) cycles keep their total-deadline accounting."""
    facade = _facade()
    original_solve = facade._solver.solve
    observed = []

    def record_budget(*args, **kwargs) -> object:
        observed.append(kwargs["wall_time_s"])
        return original_solve(*args, **kwargs)

    monkeypatch.setattr(facade._solver, "solve", record_budget)
    assert facade.solve(_input(None)).feasible
    assert observed[0] >= _SOLVER_RESERVATION_FLOOR_S
    assert observed[0] <= 20.0 - facade._config.acceptance_reservation_s


def test_hard_row_rejects_crossing_with_midpoint_outside_grid() -> None:
    island = box(-1, 299, 1, 301)
    field = compile_static_field(_input(_enc(island)))
    config = MidMpcConfig(horizon_steps=2, dt_s=100.0, strict_slack_bounds=True)
    problem = MidMpcProblem(
        own_ship=MidMpcOwnShip(psi_rad=0.0, u_mps=5.0),
        route_bearing_rad=0.0,
        planned_speed_mps=5.0,
        heading_bounds_rad=(-1.0, 1.0),
        speed_bounds_mps=(0.0, 8.0),
        cpa_safe_m=150.0,
        cpa_hard_m=50.0,
        rot_max_rad_s=0.05,
        decel_max_mps2=0.3,
        lateral_active=False,
        preferred_side=0,
        starboard_asymmetry_active=False,
        min_alteration_rad=0.0,
        route_frame=MidMpcRouteFrame(
            origin_m=(0.0, 0.0), normal=(0.0, 1.0), bearing_rad=0.0, lateral_scale_m=1000.0, weight=1.0
        ),
        static_field=field,
    )
    parameters = _pack_parameters(config, problem)
    # The first 500 m segment crosses the island at 300 m, but its midpoint
    # (250 m) lies outside the chart grid. L4 is not involved in this test.
    assert 250.0 < field.north_min_m
    rows = _static_rows(ca.DM([0.0, 0.0]), ca.DM([5.0, 5.0]), ca.DM(parameters), config, problem, len(parameters) - 2)
    assert float(ca.vertcat(*rows)[0]) < 0.0
    assert LineString([(0.0, 0.0), (0.0, 500.0)]).intersects(island)
