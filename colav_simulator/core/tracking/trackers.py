"""trackers.py.

Summary:
Contains class definitions for dynamic obstacle
target trackers. Every tracker must adhere to the
ITracker interface.

Author: Trym Tengesdal
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np
import scipy.linalg as la

import colav_simulator.common.config_parsing as cp
import colav_simulator.core.sensing as sens


class TrackStatus(StrEnum):
    """Association status owned by the tracker."""

    UPDATED = "updated"
    COASTING = "coasting"
    TERMINATED = "terminated"


@dataclass(frozen=True)
class TrackKey:
    """Stable target identity within one tracker generation."""

    target_id: int
    generation: int

    def __post_init__(self) -> None:
        """Validate the target identity generation."""
        if self.target_id < 0:
            raise ValueError("target_id must be non-negative")
        if self.generation < 1:
            raise ValueError("generation must be positive")


def track_key_sort(key: TrackKey) -> tuple[int, int]:
    """Return the canonical target-id then generation ordering key."""
    if not isinstance(key, TrackKey):
        raise TypeError("track_key_sort requires TrackKey")
    return key.target_id, key.generation


@dataclass(frozen=True)
class TrackSnapshot(Sequence[Any]):
    """Immutable tracker-authoritative observation with legacy tuple access."""

    key: TrackKey
    state: np.ndarray
    covariance: np.ndarray
    length_m: float
    width_m: float
    observed_at_s: float
    generated_at_s: float
    status: TrackStatus
    source: str

    def __post_init__(self) -> None:
        """Freeze and validate tracker output arrays and metadata."""
        state = np.asarray(self.state, dtype=float).copy()
        covariance = np.asarray(self.covariance, dtype=float).copy()
        if state.shape != (4,):
            raise ValueError("track state must have shape (4,)")
        if covariance.shape != (4, 4):
            raise ValueError("track covariance must have shape (4, 4)")
        if not np.all(np.isfinite(state)) or not np.all(np.isfinite(covariance)):
            raise ValueError("track state and covariance must be finite")
        if self.length_m <= 0.0 or self.width_m <= 0.0:
            raise ValueError("track dimensions must be positive")
        if not np.allclose(covariance, covariance.T, rtol=0.0, atol=1.0e-10):
            raise ValueError("track covariance must be symmetric")
        if float(np.min(np.linalg.eigvalsh(covariance))) < -1.0e-9:
            raise ValueError("track covariance must be positive semidefinite")
        if not np.isfinite((self.observed_at_s, self.generated_at_s)).all():
            raise ValueError("track times must be finite")
        if self.observed_at_s < 0.0:
            raise ValueError("observation time must be non-negative")
        if self.observed_at_s > self.generated_at_s:
            raise ValueError("observation time cannot be after generation time")
        if not self.source:
            raise ValueError("track source must be non-empty")
        state.setflags(write=False)
        covariance.setflags(write=False)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "covariance", covariance)

    @property
    def target_id(self) -> int:
        return self.key.target_id

    @property
    def age_s(self) -> float:
        return self.generated_at_s - self.observed_at_s

    def as_legacy_tuple(self) -> tuple[int, np.ndarray, np.ndarray, float, float]:
        return self.target_id, self.state, self.covariance, self.length_m, self.width_m

    def __len__(self) -> int:
        """Expose legacy tuple length."""
        return 5

    def __iter__(self) -> Iterator[Any]:
        """Iterate through the legacy tuple view."""
        return iter(self.as_legacy_tuple())

    def __getitem__(self, index: int | slice) -> Any:
        """Index the legacy tuple view."""
        return self.as_legacy_tuple()[index]


class ITracker(ABC):
    @abstractmethod
    def track(
        self,
        t: float,
        dt: float,
        true_do_states: list[tuple[int, np.ndarray, float, float]],
        ownship_state: np.ndarray,
    ) -> tuple[list[tuple[int, np.ndarray, np.ndarray, float, float]], list[tuple[int, np.ndarray]]]:
        """Tracks/updates estimates on dynamic obstacles.

        Based on sensor measurements generated from the input true dynamic obstacle
        states.

        Args:
            t (float): Current time (assumed >= 0).
            dt (float): Time since last update.
            true_do_states (list[tuple[int, np.ndarray, float, float]]): List of
                tuples of true dynamic obstacle indices and states (do_idx, [x, y,
                Vx, Vy], length, width) x n_do. Used for simulating sensor
                measurements.
            ownship_state (np.ndarray): Ownship state vector on the form [x, y, Vx,
                Vy] used for simulating sensor measurements.

        Returns:
            tuple[list[tuple[int, np.ndarray, np.ndarray, float, float]], list[tuple[int, np.ndarray]]]:
                List of updated dynamic obstacle tracks (ID, state, cov, length,
                width), sorted in ascending order by the distance from the ownship.
                Also, a list the sensor measurements used.
        """

    @abstractmethod
    def set_sensor_list(self, sensor_list: list[sens.ISensor]) -> None:
        """Sets the sensor list for the tracker.

        Args:
            sensor_list (List[sens.ISensor]): List of sensors used by the tracker.
        """

    @abstractmethod
    def get_track_information(
        self, ownship_state: np.ndarray
    ) -> tuple[list[tuple[int, np.ndarray, np.ndarray, float, float]], list[float]]:
        """Returns the dynamic obstacle track information.

        Returns (ID, state, cov, length, width), sorted in ascending order by the
        distance from the ownship. Also, it returns the associated Normalized
        Innovation error Squared (NIS) values for the most recent update step for
        each track, and the track labels.

        Args:
            ownship_state (np.ndarray): Ownship state vector on the form [x, y, Vx,
                Vy] used for simulating sensor measurements.

        Returns:
            tuple[list[tuple[int, np.ndarray, np.ndarray, float, float]], list[float]]:
                List of tracks and list of NISes.
        """

    @abstractmethod
    def reset(self) -> None:
        """Resets the tracker to its initial state."""


@dataclass
class KFParams:
    """Class for holding KF parameters."""

    P_0: np.ndarray = field(default_factory=lambda: np.diag([49.0, 49.0, 0.5, 0.5]))
    q: float = 0.4

    def to_dict(self) -> dict:  # noqa: D102
        output_dict = {"P_0": self.P_0.diagonal().tolist(), "q": self.q}
        return output_dict

    @classmethod
    def from_dict(cls, config_dict: dict) -> "KFParams":  # noqa: D102
        return KFParams(P_0=np.diag(config_dict["P_0"]), q=config_dict["q"])


@dataclass
class Config:
    """Class for holding tracker configuration parameters."""

    god_tracker: bool | None = True
    kf: KFParams | None = None

    def to_dict(self) -> dict:  # noqa: D102
        output_dict = {}
        if self.kf is not None:
            output_dict["kf"] = self.kf.to_dict()
        if self.god_tracker is not None:
            output_dict["god_tracker"] = ""

        return output_dict

    @classmethod
    def from_dict(cls, config_dict: dict) -> "Config":  # noqa: D102
        config = Config()

        if "kf" in config_dict:
            config.kf = cp.convert_settings_dict_to_dataclass(KFParams, config_dict["kf"])
            config.god_tracker = None
        elif "god_tracker" in config_dict:
            config.god_tracker = True
            config.kf = None

        return config


class TrackerBuilder:
    @classmethod
    def construct_tracker(cls, sensors: list, config: Config | None = None) -> ITracker:
        """Builds a tracker from the configuration.

        Args:
            sensors (list): Sensors used by the tracker.
            config (Optional[Config]): Tracker configuration. Defaults to None.

        Returns:
            ITracker: The tracker.
        """
        if config and config.kf:
            return KF(sensors, config.kf)
        elif config and config.god_tracker:
            return GodTracker(sensors)
        else:
            return KF(sensors)


class GodTracker(ITracker):
    """This tracker is used to simulate perfect knowledge of dynamic obstacles."""

    def __init__(self, sensor_list: list[sens.ISensor] | None = None) -> None:
        self.sensors: list[sens.ISensor] = sensor_list

        self._initialized: bool = False
        self._labels: list = []
        self._xs_upd: list = []
        self._P_upd: list = []
        self._length_upd: list = []
        self._t_prev: float = -1.0
        self._width_upd: list = []
        self._recent_sensor_measurements: list = []
        self._generations: dict[int, int] = {}
        self._snapshots: list[TrackSnapshot] = []

    def reset(self) -> None:
        self._initialized = False
        self._labels = []
        self._xs_upd = []
        self._P_upd = []
        self._length_upd = []
        self._t_prev = -1.0
        self._width_upd = []
        self._recent_sensor_measurements = []
        self._generations = {}
        self._snapshots = []

    def set_sensor_list(self, sensor_list: list[sens.ISensor]) -> None:
        self.sensors = sensor_list

    def track(
        self,
        t: float,
        dt: float,  # noqa: ARG002
        true_do_states: list[tuple[int, np.ndarray, float, float]],
        ownship_state: np.ndarray,
    ) -> tuple[list[TrackSnapshot], list[tuple[int, np.ndarray]]]:
        # If the function is run at the same time as the previous, return the same tracks
        if self.sensors is None:
            msg = "Sensor list must be set."
            raise ValueError(msg)
        if t <= self._t_prev:
            tracks, _ = self.get_track_information(ownship_state)
            return tracks, self._recent_sensor_measurements

        self._t_prev = t

        # Perfect knowledge is a snapshot of the targets active at this time.
        # Rebuilding all parallel arrays together preserves target identity when
        # a lower-numbered vessel reaches the end of its active interval.
        previous_labels = set(self._labels)
        self._labels = [do_idx for do_idx, _, _, _ in true_do_states]
        for label in self._labels:
            if label not in previous_labels:
                self._generations[label] = self._generations.get(label, 0) + 1
        self._xs_upd = [np.asarray(do_state, dtype=float).copy() for _, do_state, _, _ in true_do_states]
        self._P_upd = [np.zeros((4, 4)) for _ in true_do_states]
        self._length_upd = [do_length for _, _, do_length, _ in true_do_states]
        self._width_upd = [do_width for _, _, _, do_width in true_do_states]
        self._snapshots = [
            TrackSnapshot(
                key=TrackKey(target_id=label, generation=self._generations[label]),
                state=self._xs_upd[i],
                covariance=self._P_upd[i],
                length_m=self._length_upd[i],
                width_m=self._width_upd[i],
                observed_at_s=t,
                generated_at_s=t,
                status=TrackStatus.UPDATED,
                source="god",
            )
            for i, label in enumerate(self._labels)
        ]

        # Only generate measurements for initialized tracks
        sensor_measurements = []
        for sensor in self.sensors:
            z = sensor.generate_measurements(t, true_do_states, ownship_state)
            sensor_measurements.append(z)
        self._recent_sensor_measurements = sensor_measurements

        tracks_sorted_by_distance = sorted(
            self._snapshots,
            key=lambda snapshot: np.linalg.norm(snapshot.state[:2] - ownship_state[:2]),
        )
        return tracks_sorted_by_distance, sensor_measurements

    def get_track_information(self, ownship_state: np.ndarray) -> tuple[list, list]:
        tracks_sorted_by_distance = sorted(
            self._snapshots,
            key=lambda snapshot: np.linalg.norm(snapshot.state[:2] - ownship_state[:2]),
        )
        return tracks_sorted_by_distance, [0.0 for _ in range(len(tracks_sorted_by_distance))]


class KF(ITracker):
    """The KF class implements a linear Kalman filter based tracker."""

    def __init__(self, sensor_list: list[sens.ISensor] | None = None, params: KFParams | None = None) -> None:
        if params is not None:
            self._params: KFParams = params
        else:
            self._params = KFParams()

        self._model = CVModel(self._params.q)

        self.sensors: list[sens.ISensor] = sensor_list

        self._track_initialized: list = []
        self._track_terminated: list = []
        self._labels: list = []
        self._xs_p: list = []
        self._P_p: list = []
        self._xs_upd: list = []
        self._P_upd: list = []
        self._length_upd: list = []  # List of DO length estimates. Assumed known
        self._width_upd: list = []  # List of DO width estimates. Assumed known
        self._NIS: list = []
        self._t_prev: float = -1.0
        self._recent_sensor_measurements: list = []
        self._generations: dict[int, int] = {}
        self._observed_at_s: list[float] = []
        self._statuses: list[TrackStatus] = []
        self._snapshots: list[TrackSnapshot] = []

    def reset(self) -> None:
        self._track_initialized = []
        self._track_terminated = []
        self._labels = []
        self._xs_p = []
        self._P_p = []
        self._xs_upd = []
        self._P_upd = []
        self._length_upd = []
        self._width_upd = []
        self._NIS = []
        self._t_prev = -1.0
        self._recent_sensor_measurements = []
        self._generations = {}
        self._observed_at_s = []
        self._statuses = []
        self._snapshots = []

    def set_sensor_list(self, sensor_list: list[sens.ISensor]) -> None:
        self.sensors = sensor_list

    def track(  # noqa: PLR0912
        self,
        t: float,
        dt: float,
        true_do_states: list[tuple[int, np.ndarray, float, float]],
        ownship_state: np.ndarray,
    ) -> tuple[list[tuple[int, np.ndarray, np.ndarray, float, float]], list[tuple[int, np.ndarray]]]:
        if self.sensors is None:
            msg = "Sensor list must be set."
            raise ValueError(msg)
        # If the function is run at the same time as the previous, return the same tracks
        if t <= self._t_prev:
            tracks, _ = self.get_track_information(ownship_state)
            return tracks, self._recent_sensor_measurements

        self._t_prev = t
        max_sensor_range = max(sensor.max_range for sensor in self.sensors)
        for _i, (do_idx, do_state, do_length, do_width) in enumerate(true_do_states):
            dist_ownship_to_do = np.linalg.norm(do_state[:2] - ownship_state[:2])
            if do_idx not in self._labels and dist_ownship_to_do < max_sensor_range:
                self._generations[do_idx] = self._generations.get(do_idx, 0) + 1
                self._labels.append(do_idx)
                self._track_initialized.append(False)
                self._track_terminated.append(False)
                self._xs_upd.append(do_state)
                self._P_upd.append(self._params.P_0)
                self._xs_p.append(do_state)
                self._P_p.append(self._params.P_0)
                self._length_upd.append(do_length)
                self._width_upd.append(do_width)
                self._NIS.append(np.nan)
                self._observed_at_s.append(t)
                self._statuses.append(TrackStatus.COASTING)
            elif do_idx in self._labels:
                self._track_initialized[self._labels.index(do_idx)] = True

        n_tracked_do = len(self._xs_upd)
        sensor_measurements = []
        for sensor in self.sensors:
            z = sensor.generate_measurements(t, true_do_states, ownship_state)
            sensor_measurements.append(z)
        self._recent_sensor_measurements = sensor_measurements

        tracks = []
        for i in range(n_tracked_do):
            measurement_used = False
            if self._track_initialized[i] and not self._track_terminated[i]:
                self._xs_p[i], self._P_p[i] = self.predict(self._xs_upd[i], self._P_upd[i], dt)
                self._xs_upd[i] = self._xs_p[i]
                self._P_upd[i] = self._P_p[i]

                if sensor_measurements:
                    for sensor_id in range(len(self.sensors)):
                        sensed_dos = [do_meas[0] for do_meas in sensor_measurements[sensor_id]]

                        if self._labels[i] in sensed_dos:  # Automatic data association
                            z = sensor_measurements[sensor_id][sensed_dos.index(self._labels[i])][1]

                            self._xs_upd[i], self._P_upd[i], NIS_i = self.update(
                                self._xs_upd[i], self._P_upd[i], z, sensor_id
                            )

                            if not np.isnan(NIS_i):
                                self._NIS[i] = NIS_i
                                measurement_used = True

            self._statuses[i] = TrackStatus.UPDATED if measurement_used else TrackStatus.COASTING
            if measurement_used:
                self._observed_at_s[i] = t

        self._snapshots = [
            TrackSnapshot(
                key=TrackKey(self._labels[i], self._generations[self._labels[i]]),
                state=self._xs_upd[i],
                covariance=self._P_upd[i],
                length_m=self._length_upd[i],
                width_m=self._width_upd[i],
                observed_at_s=self._observed_at_s[i],
                generated_at_s=t,
                status=self._statuses[i],
                source="kf",
            )
            for i in range(n_tracked_do)
            if not self._track_terminated[i]
        ]

        # print(f"xs_p: {self._xs_p}, xs_upd: {self._xs_upd}")
        # print(f"P_p: {self._P_p}")
        # print(f"P_upd: {self._P_upd}")
        tracks_sorted_by_distance = sorted(
            self._snapshots,
            key=lambda snapshot: np.linalg.norm(snapshot.state[:2] - ownship_state[:2]),
        )
        return tracks_sorted_by_distance, sensor_measurements

    def predict(self, xs_upd: np.ndarray, P_upd: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
        F = self._model.F(dt)
        Q = self._model.Q(dt)

        x_pred = self._model.f(xs_upd, dt)
        P_pred = F @ P_upd @ F.T + Q

        return x_pred, P_pred

    def innovation(self, xs_p: np.ndarray, P_p: np.ndarray, z: np.ndarray, sensor_id: int) -> tuple[np.ndarray, np.ndarray]:
        zbar = self.sensors[sensor_id].h(xs_p)
        v = z - zbar

        H = self.sensors[sensor_id].H(xs_p)
        R = self.sensors[sensor_id].R(xs_p)
        S = H @ P_p @ H.T + R

        return v, S

    def update(
        self, xs_p: np.ndarray, P_p: np.ndarray, z: np.ndarray, sensor_id: int
    ) -> tuple[np.ndarray, np.ndarray, float]:
        if any(np.isnan(z)):
            return xs_p, P_p, np.nan

        v, S = self.innovation(xs_p, P_p, z, sensor_id)
        H = self.sensors[sensor_id].H(xs_p)

        K = P_p @ H.T @ la.inv(S)
        x_upd = xs_p + K @ v
        P_upd = P_p - K @ H @ P_p

        return x_upd, P_upd, NIS(v, S)

    def get_track_information(self, ownship_state: np.ndarray) -> tuple[list, list]:
        tracks_sorted_by_distance = sorted(
            self._snapshots,
            key=lambda snapshot: np.linalg.norm(snapshot.state[:2] - ownship_state[:2]),
        )
        return tracks_sorted_by_distance, [0.0 for _ in range(len(tracks_sorted_by_distance))]


def NIS(v: np.ndarray, S: np.ndarray) -> float:
    """Calculate the Normalized Innovation Squared (NIS).

    Args:
        v (np.ndarray): Innovation vector.
        S (np.ndarray): Innovation covariance matrix.

    Returns:
        float: NIS value.
    """
    return v.T @ la.inv(S) @ v


class CVModel:
    """The CVModel class implements a constant velocity model."""

    def __init__(self, q: float) -> None:
        self._q: float = q

    def f(self, xs: np.ndarray, dt: float) -> np.ndarray:
        """Returns the r.h.s of the prediction model state transition function.

        Args:
            xs (np.ndarray): State vector [x, y, Vx, Vy]
            dt (float): Time step

        Returns:
            np.ndarray: New state vector dt seconds ahead

        """
        return xs + np.array([xs[2] * dt, xs[3] * dt, 0.0, 0.0])

    def F(self, dt: float) -> np.ndarray:
        """Returns the Jacobian of the prediction model state transition function.

        Args:
            xs (np.ndarray): xs (np.ndarray): State vector [x, y, Vx, Vy]
            dt (float): Time step

        Returns:
            np.ndarray: Jacobian of the prediction model state transition function
        """
        return np.array(
            [
                [1.0, 0.0, dt, 0.0],
                [0.0, 1.0, 0.0, dt],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )

    def Q(self, dt: float) -> np.ndarray:
        """Returns the process noise covariance matrix.

        Args:
            dt (float): Time step

        Returns:
            np.ndarray: Process noise covariance matrix
        """
        return (
            np.array(
                [
                    [dt**3 / 3.0, 0.0, dt**2 / 2.0, 0.0],
                    [0.0, dt**3 / 3.0, 0.0, dt**2 / 2.0],
                    [dt**2 / 2.0, 0.0, dt, 0.0],
                    [0.0, dt**2 / 2.0, 0.0, dt],
                ]
            )
            * self._q
        )
