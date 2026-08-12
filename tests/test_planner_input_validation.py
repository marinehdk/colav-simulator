import numpy as np
import pytest

from colav_simulator.core.colav.custom_mpc_adapter import PlannerInput, TrackedObstacle


def valid_track(**overrides) -> TrackedObstacle:
    values = {
        "target_id": 1,
        "state_enu": np.array([100.0, 25.0, -2.0, 0.0]),
        "covariance": np.eye(4),
        "length_m": 8.45,
        "width_m": 3.0,
        "observed_at_s": 2.0,
        "age_s": 0.0,
    }
    values.update(overrides)
    return TrackedObstacle(**values)


def valid_input(**overrides) -> PlannerInput:
    values = {
        "sim_time_s": 2.0,
        "dt_sim_s": 0.5,
        "waypoints_enu_m": np.array([[0.0, 100.0], [0.0, 0.0]]),
        "speed_plan_mps": np.array([4.0, 4.0]),
        "ownship_state": np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0]),
        "tracks": (valid_track(),),
        "enc": None,
        "goal_state": None,
        "disturbance": None,
        "algorithm_seed": 4,
    }
    values.update(overrides)
    return PlannerInput(**values)


def test_planner_input_copies_arrays_and_preserves_enu_si_rad_contract() -> None:
    source = np.array([0.0, 0.0, 0.0, 4.0, 0.0, 0.0])
    planner_input = valid_input(ownship_state=source)
    source[0] = 99.0

    assert planner_input.ownship_state[0] == 0.0
    assert planner_input.ownship_state.flags.writeable is False
    assert (planner_input.coordinate_frame, planner_input.linear_unit, planner_input.angle_unit) == (
        "ENU",
        "SI",
        "rad",
    )


def test_planner_input_preserves_active_plant_controller_identity() -> None:
    planner_input = valid_input(
        ownship_model="Viknes",
        ownship_controller="FLSC",
        ownship_max_turn_rate_rad_s=np.deg2rad(3.0),
    )

    assert planner_input.ownship_model == "Viknes"
    assert planner_input.ownship_controller == "FLSC"
    assert planner_input.ownship_max_turn_rate_rad_s == pytest.approx(np.deg2rad(3.0))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"covariance": np.diag([1.0, 1.0, 1.0, -0.1])}, "positive semidefinite"),
        (
            {
                "covariance": np.array(
                    [
                        [1.0, 1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0, 0.0],
                        [0.0, 0.0, 1.0, 0.0],
                        [0.0, 0.0, 0.0, 1.0],
                    ]
                )
            },
            "symmetric",
        ),
        ({"state_enu": np.array([0.0, np.nan, 0.0, 0.0])}, "finite"),
        ({"target_id": -1}, "non-negative"),
        ({"length_m": 0.0}, "positive"),
    ],
)
def test_tracked_obstacle_rejects_invalid_geometry_and_covariance(overrides, message) -> None:
    with pytest.raises(ValueError, match=message):
        valid_track(**overrides)


def test_planner_input_rejects_duplicate_tracks_and_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="unique"):
        valid_input(tracks=(valid_track(), valid_track()))
    with pytest.raises(TypeError, match="TrackedObstacle"):
        valid_input(tracks=("not-a-track",))
    with pytest.raises(ValueError, match="align"):
        valid_input(speed_plan_mps=np.array([4.0]))
    with pytest.raises(ValueError, match="shape"):
        valid_input(ownship_state=np.zeros(4))


def test_planner_input_rejects_unfrozen_units() -> None:
    with pytest.raises(ValueError, match="ENU/SI/rad"):
        valid_input(angle_unit="deg")


def test_tracked_obstacle_rejects_nonfinite_metadata() -> None:
    with pytest.raises(ValueError, match="finite"):
        valid_track(age_s=np.nan)
    with pytest.raises(ValueError, match="finite"):
        valid_track(length_m=np.inf)
