import numpy as np
import pytest
from shapely.ops import unary_union

from colav_simulator.common.map_functions import create_ship_polygon
from colav_simulator.core.collision import (
    VesselPose,
    continuous_footprint_collision,
    rectangular_footprint,
)
from colav_simulator.simulator import Config, Simulator


def pose(north: float, east: float, heading: float = 0.0, length: float = 2.0, width: float = 2.0) -> VesselPose:
    return VesselPose(north, east, heading, length, width)


def collided(a0: VesselPose, a1: VesselPose, b0: VesselPose, b1: VesselPose, tolerance: float = 0.25) -> bool:
    return continuous_footprint_collision(
        a0,
        a1,
        b0,
        b1,
        step_tolerance_m=tolerance,
    ) is not None


def test_rectangular_footprint_has_exact_dimensions_and_center() -> None:
    footprint = rectangular_footprint(pose(12.0, 5.0, np.deg2rad(31.0), length=8.0, width=3.0))
    helper = create_ship_polygon(12.0, 5.0, np.deg2rad(31.0), 8.0, 3.0)

    assert footprint.area == pytest.approx(24.0)
    assert footprint.centroid.x == pytest.approx(5.0)
    assert footprint.centroid.y == pytest.approx(12.0)
    assert len(footprint.exterior.coords) - 1 == 4
    assert footprint.equals_exact(helper, tolerance=1e-12)


def test_static_overlap_contact_and_separation() -> None:
    own = pose(0.0, 0.0)
    assert collided(own, own, pose(0.0, 0.0), pose(0.0, 0.0))
    assert collided(own, own, pose(2.0, 0.0), pose(2.0, 0.0))
    assert not collided(own, own, pose(2.1, 0.0), pose(2.1, 0.0))


def test_high_speed_head_on_tunneling_is_detected_between_timestamps() -> None:
    own_start, own_end = pose(-10.0, 0.0), pose(10.0, 0.0)
    target = pose(0.0, 0.0)

    assert not rectangular_footprint(own_start).intersects(rectangular_footprint(target))
    assert not rectangular_footprint(own_end).intersects(rectangular_footprint(target))
    assert collided(own_start, own_end, target, target)


def test_high_speed_perpendicular_crossing_is_detected() -> None:
    assert collided(
        pose(-10.0, 0.0),
        pose(10.0, 0.0),
        pose(0.0, -10.0, np.pi / 2.0),
        pose(0.0, 10.0, np.pi / 2.0),
    )


def test_synchronized_check_rejects_independent_swept_union_false_positive() -> None:
    own_start, own_end = pose(-10.0, 0.0), pose(10.0, 0.0)
    target_start, target_end = pose(10.0, 0.0), pose(30.0, 0.0)
    own_sweep = unary_union([rectangular_footprint(own_start), rectangular_footprint(own_end)]).convex_hull
    target_sweep = unary_union([rectangular_footprint(target_start), rectangular_footprint(target_end)]).convex_hull

    assert own_sweep.intersects(target_sweep)
    assert not collided(own_start, own_end, target_start, target_end)


def test_rotation_sweep_collision_is_detected_between_endpoints() -> None:
    own_start = pose(0.0, 0.0, 0.0, length=10.0, width=1.0)
    own_end = pose(0.0, 0.0, np.pi / 2.0, length=10.0, width=1.0)
    target = pose(3.5, 3.5, length=1.0, width=1.0)

    assert not rectangular_footprint(own_start).intersects(rectangular_footprint(target))
    assert not rectangular_footprint(own_end).intersects(rectangular_footprint(target))
    assert collided(own_start, own_end, target, target)


def test_collision_boolean_converges_across_configured_tolerances() -> None:
    case = (
        pose(-10.0, 0.0),
        pose(10.0, 0.0),
        pose(0.0, -10.0, np.pi / 2.0),
        pose(0.0, 10.0, np.pi / 2.0),
    )
    assert [collided(*case, tolerance=value) for value in (0.5, 0.25, 0.125)] == [True, True, True]


def test_simulator_reports_only_colliding_pairs_with_oracle_evidence() -> None:
    class ShipFixture:
        def __init__(self, ship_id: int, state: np.ndarray) -> None:
            self.id = ship_id
            self.state = state
            self.length = 2.0
            self.width = 2.0
            self.t_start = 0.0

    simulator = Simulator.__new__(Simulator)
    simulator.config = Config()
    simulator.ship_list = [
        ShipFixture(0, np.zeros(6)),
        ShipFixture(1, np.zeros(6)),
        ShipFixture(2, np.array([20.0, 0.0, 0.0, 0.0, 0.0, 0.0])),
    ]
    poses = [simulator._vessel_pose(ship) for ship in simulator.ship_list]
    simulator._motion_segments = [(value, value) for value in poses]
    simulator._motion_interval = (4.0, 4.5)

    collisions = simulator.detect_ship_collisions(0)

    assert simulator.determine_ship_collision(0) is True
    assert [item["target_id"] for item in collisions] == [1]
    assert collisions[0]["oracle_id"] == "footprint-adaptive-v1"
    assert collisions[0]["interval_start_s"] <= collisions[0]["interval_end_s"]


def test_simulator_config_rejects_nonpositive_collision_tolerance() -> None:
    with pytest.raises(ValueError, match="positive"):
        Config(ccd_step_tolerance_m=0.0)
