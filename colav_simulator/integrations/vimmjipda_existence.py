"""vimmjipda_existence.py.

Summary:
P3-S5 (spec #90) adapter that elevates the external VIMMJIPDA tracker's
existence probability to a first-class :class:`TrackSnapshot` field without
touching the external repo (``$COLAV_ECOSYSTEM_ROOT/vimmjipda``). The inner
interface returns legacy 5-tuples plus NaN NIS; the per-track
``track.existence_probability`` recursion lives in the external manager
(``code/tracking/trackers.py`` predict/update chain — the internal P_D /
visibility update is external-domain and stays opaque here).

The adapter delegates tracking 1:1 and re-publishes every track as a
``TrackSnapshot`` (existence from the manager track index map; snapshots mirror
the inner output tuples exactly, including the extremity-filtered ``track``
path and the unfiltered ``get_track_information`` path).
"""

from typing import Any

import numpy as np

import colav_simulator.core.sensing as cs_sensing
import colav_simulator.core.tracking.trackers as cs_trackers


class VIMMJIPDAExistenceAdapter(cs_trackers.ITracker):
    """ITracker facade over the external VIMMJIPDA with snapshot existence output."""

    source_label = "vimmjipda"

    def __init__(self, inner: Any) -> None:
        self._inner = inner

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

    def _snapshot(self, raw: tuple, existence: float, observed_at_s: float, generated_at_s: float) -> cs_trackers.TrackSnapshot:
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
            # The external VIMMJIPDA interface fuses the Radar channel only
            # (sensor-model-v1 §2 radar_x = 1).
            sources=(cs_trackers.TrackSource(sensor_id=1, last_seen_age_s=0.0),),
        )

    def track(
        self,
        t: float,
        dt: float,
        true_do_states: list[tuple[int, np.ndarray, float, float]],
        ownship_state: np.ndarray,
    ) -> tuple[list[cs_trackers.TrackSnapshot], list[tuple[int, np.ndarray]]]:
        tracks, sensor_measurements = self._inner.track(t, dt, true_do_states, ownship_state)
        existence = self._existence_by_index()
        snapshots = [
            self._snapshot(raw, existence.get(int(raw[0]), 1.0), observed_at_s=max(0.0, float(t) - dt), generated_at_s=t)
            for raw in tracks
        ]
        return snapshots, sensor_measurements

    def set_sensor_list(self, sensor_list: list[cs_sensing.ISensor]) -> None:
        self._inner.set_sensor_list(sensor_list)

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
