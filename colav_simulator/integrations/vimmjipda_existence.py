"""vimmjipda_existence.py.

Summary:
P3-S5 (spec #90) adapter that elevates the external VIMMJIPDA tracker's
existence probability to a first-class :class:`TrackSnapshot` field without
touching the external repo (``$COLAV_ECOSYSTEM_ROOT/vimmjipda``). The inner
interface returns legacy 5-tuples plus NaN NIS; the per-track
``track.existence_probability`` recursion lives in the external manager
(``code/tracking/trackers.py`` predict/update chain — the internal P_D /
visibility update is external-domain and stays opaque here).

The adapter retains the external tracker and re-publishes every track as a
``TrackSnapshot`` (existence from the manager track index map; snapshots mirror
the inner output tuples exactly, including the extremity-filtered ``track``
path and the unfiltered ``get_track_information`` path).
RadarXBand's range-dependent clutter intensity is supplied to association
odds; the native uniform background remains a conservative lower bound.
"""

from typing import Any

import numpy as np

import colav_simulator.core.sensing as cs_sensing
import colav_simulator.core.tracking.trackers as cs_trackers


class _RadarClutterAssociator:
    """Adapt per-measurement clutter odds to the native scalar-density API.

    The native associator uses w_ij / lambda in both exact and Murty paths.
    Scaling each measurement column by lambda_native / lambda(position)
    supplies the same odds without changing its hypotheses or IPDA recursion.
    Missed-detection weights, confirmation thresholds and track outputs stay
    under the external manager's authority.
    """

    def __init__(self, inner: Any, radars: tuple[cs_sensing.RadarXBand, ...]) -> None:
        self.inner = inner
        self.radars = radars
        self.ownship_ne = np.zeros(2)

    def get_marginal_association_probabilities(self, cluster: Any) -> np.ndarray:
        if not cluster.n_measurements:
            return self.inner.get_marginal_association_probabilities(cluster)
        densities = []
        for measurement in cluster.measurements:
            # External measurements use EN, while simulator positions use NE.
            distance = float(np.linalg.norm(np.asarray(measurement.value)[::-1] - self.ownship_ne))
            density = 0.0
            for radar in self.radars:
                if distance > radar.active_range_m:
                    continue
                params = radar.params
                radius = max(distance, radar.blind_ring_m)
                sea_factor = 10.0 ** (0.1 * params.clutter_db_per_beaufort * (params.sea_state_beaufort - 3.0))
                density += (
                    params.clutter_rate_per_m2
                    * sea_factor
                    * (params.clutter_ref_range_m / radius) ** params.clutter_range_decay
                )
            densities.append(max(float(cluster.clutter_density), density))
        original_weights = cluster.w
        cluster.w = original_weights.copy()
        cluster.w[:, : cluster.n_measurements] *= float(cluster.clutter_density) / np.asarray(densities)
        try:
            return self.inner.get_marginal_association_probabilities(cluster)
        finally:
            cluster.w = original_weights


class VIMMJIPDAExistenceAdapter(cs_trackers.ITracker):
    """ITracker facade over the external VIMMJIPDA with snapshot existence output."""

    source_label = "vimmjipda"

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._clutter_associator: _RadarClutterAssociator | None = None

    @property
    def inner(self) -> Any:
        return self._inner

    def _existence_by_index(self) -> dict[int, float]:
        """Read the external manager's per-track existence probabilities by index.

        The manager and its ``existence_probability`` attribute are the external
        repo's documented IPDA recursion output (vimmjipda constructs.py Track).
        Missing entries fall back to 1.0 — for this tracker a missing manager
        entry means the track never existed, and the adapter contract requires a
        finite gate in [0, 1] on every snapshot.
        """
        manager = getattr(self._inner, "_manager", None)
        existence: dict[int, float] = {}
        for track in getattr(manager, "tracks", ()) or ():
            existence[int(track.index)] = float(getattr(track, "existence_probability", 1.0))
        return existence

    def _credited_sensor_ids(self) -> tuple[int, ...]:
        """Sensor-model-v1 channel ids the external interface actually steps.

        Spec #91 multi-source wiring: the external acceptance check fuses the
        legacy Radar plus any sensor declaring the
        ``provides_ne_position_measurements`` capability (RadarXBand,
        ExternalCameraSensor), so the credited channels are derived from the
        wired sensor list instead of the previous radar-only constant.
        """
        ids = {
            cs_trackers.sensor_channel_id(sensor)
            for sensor in getattr(self._inner, "sensors", None) or ()
            if isinstance(sensor, cs_sensing.Radar)
            or getattr(sensor, "provides_ne_position_measurements", False)
        }
        return tuple(sorted(ids)) or (1,)

    def _snapshot(
        self, raw: tuple, existence: float, observed_at_s: float, generated_at_s: float
    ) -> cs_trackers.TrackSnapshot:
        target_id, state, covariance, length_m, width_m = raw
        return cs_trackers.TrackSnapshot(
            key=cs_trackers.TrackKey(target_id=int(target_id), generation=1),
            state=np.asarray(state, dtype=float),
            covariance=np.asarray(covariance, dtype=float),
            length_m=float(length_m),
            width_m=float(width_m),
            observed_at_s=float(observed_at_s),
            generated_at_s=float(generated_at_s),
            status=cs_trackers.TrackStatus.UPDATED,
            source=self.source_label,
            existence_prob=max(0.0, min(1.0, float(existence))),
            quality=cs_trackers.track_quality(status=cs_trackers.TrackStatus.UPDATED, age_s=0.0, source_count=1),
            # Channels actually fused by the external interface (spec #91:
            # legacy Radar + capability-flagged radar_x / camera sensors).
            sources=tuple(
                cs_trackers.TrackSource(sensor_id=sensor_id, last_seen_age_s=0.0)
                for sensor_id in self._credited_sensor_ids()
            ),
        )

    def track(
        self,
        t: float,
        dt: float,
        true_do_states: list[tuple[int, np.ndarray, float, float]],
        ownship_state: np.ndarray,
    ) -> tuple[list[cs_trackers.TrackSnapshot], list[tuple[int, np.ndarray]]]:
        if self._clutter_associator is not None:
            self._clutter_associator.ownship_ne = np.asarray(ownship_state[:2], dtype=float).copy()
        tracks, sensor_measurements = self._inner.track(t, dt, true_do_states, ownship_state)
        existence = self._existence_by_index()
        snapshots = [
            self._snapshot(raw, existence.get(int(raw[0]), 1.0), observed_at_s=max(0.0, float(t) - dt), generated_at_s=t)
            for raw in tracks
        ]
        return snapshots, sensor_measurements

    def set_sensor_list(self, sensor_list: list[cs_sensing.ISensor]) -> None:
        self._inner.set_sensor_list(sensor_list)
        tracker = self._inner._manager.tracker
        if self._clutter_associator is not None:
            tracker.data_associator = self._clutter_associator.inner
            self._clutter_associator = None
        radars = tuple(sensor for sensor in sensor_list if isinstance(sensor, cs_sensing.RadarXBand))
        if radars:
            self._clutter_associator = _RadarClutterAssociator(tracker.data_associator, radars)
            tracker.data_associator = self._clutter_associator

    def get_track_information(
        self, ownship_state: np.ndarray
    ) -> tuple[list[cs_trackers.TrackSnapshot], list[float]]:
        tracks, nises = self._inner.get_track_information(ownship_state)
        existence = self._existence_by_index()
        snapshots = [
            self._snapshot(raw, existence.get(int(raw[0]), 1.0), observed_at_s=0.0, generated_at_s=0.0)
            for raw in tracks
        ]
        return snapshots, list(nises)

    def reset(self) -> None:
        self._inner.reset()
