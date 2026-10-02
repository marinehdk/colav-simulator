"""AIS display-layer state semantics (P3-S4, spec #90).

Backend-authoritative AIS target state for the web AIS target layer. The web
never recomputes age or state; it renders the additive transport field
``truth[].ais = {"age_s": float, "state": "active"|"sleeping"|"lost"}`` and
only composes the *dangerous* presentation locally (IMO SN.1/Circ.243/Rev.1
defines "dangerous" as an activated target meeting the collision-avoidance
alarm criteria — that judgment already exists in the risk projection, so the
composition active+alarm happens display-side).

Symbol semantics (IMO SN.1/Circ.243/Rev.1 Annex 1, "Guidelines for the
presentation of navigation-related symbols"):
- sleeping target: acute isosceles triangle oriented by heading (COG when
  heading is absent); reported position at the triangle centre/median; smaller
  than the activated symbol; no vector.
- activated target: enlarged same shape + COG/SOG dashed speed vector + solid
  heading line (length 2x the triangle) + rate-of-turn flag.
- lost target: triangle with a thick cross through it, keeping the last
  heading, flashing until acknowledged; no vector/heading/ROT indication.
- dangerous target: bold red triangle + vector, flashing until acknowledged.

State judgment here is an automated-activation policy by speed/age thresholds
(the display has no operator activation gesture):
- ``lost`` once the target age exceeds ``AIS_LOST_AGE_FACTOR`` expected
  reporting intervals (a report interval depends on speed per ITU-R M.1371);
- ``active`` when underway at or above ``AIS_ACTIVE_SOG_MPS`` (enlarged
  symbol + vector);
- ``sleeping`` otherwise (stationary/creeping targets keep the small symbol).

Report cadence: ITU-R M.1371 autonomous-mode scheduled intervals — the same
table the tracker AIS sensor implements (``sensing.py`` ``AIS._measurement_rate``):
Class A moored/anchored ~0 kn -> 180 s, 0-14 kn -> 10 s, 14-23 kn -> 6 s,
>23 kn -> 2 s; Class B <=2 kn -> 180 s, >2 kn -> 30 s.
"""

from __future__ import annotations

import math

MPS_PER_KNOT = 1852.0 / 3600.0

# Display policy: underway threshold separating "active" (vector shown) from
# "sleeping" (stationary symbol). Sits between the ITU moored boundary (~0 kn)
# and the Class B slow-cadence boundary (2 kn); ~0.97 kn.
AIS_ACTIVE_SOG_MPS = 0.5

# Display policy: a target is "lost" after this many consecutive expected
# reporting intervals without a position report (~3 missed reports).
AIS_LOST_AGE_FACTOR = 3.0

_AIS_CLASS_A_SOG_KN_ANCHORED = 0.001
_AIS_CLASS_A_SOG_KN_MODERATE = 14.0
_AIS_CLASS_A_SOG_KN_FAST = 23.0
_AIS_CLASS_B_SOG_KN_SLOW = 2.0


def ais_reporting_interval_s(sog_mps: float, ais_class: str = "A") -> float:
    """Expected AIS autonomous-mode position-report interval in seconds.

    Mirrors the rate table documented on ``sensing.AIS`` (ITU-R M.1371);
    ``ais_class`` is ``"A"`` or ``"B"`` (anything else falls back to Class A).
    """
    sog_knots = float(sog_mps) / MPS_PER_KNOT
    if str(ais_class).upper() == "B":
        return 180.0 if sog_knots <= _AIS_CLASS_B_SOG_KN_SLOW else 30.0
    if sog_knots <= _AIS_CLASS_A_SOG_KN_ANCHORED:
        return 180.0
    if sog_knots <= _AIS_CLASS_A_SOG_KN_MODERATE:
        return 10.0
    if sog_knots <= _AIS_CLASS_A_SOG_KN_FAST:
        return 6.0
    return 2.0


def ais_lost_age_s(sog_mps: float, ais_class: str = "A") -> float:
    """Age beyond which the target is displayed as lost (IMO 243 semantics)."""
    return AIS_LOST_AGE_FACTOR * ais_reporting_interval_s(sog_mps, ais_class)


def ais_target_state(sog_mps: float, age_s: float, ais_class: str = "A") -> str:
    """Pure AIS display-state judgment (backend authority; web does not recompute).

    Args:
        sog_mps: current speed over ground in m/s.
        age_s: seconds since the last AIS position report (display clock).
        ais_class: ``"A"`` or ``"B"`` reporting vocabulary.

    Returns:
        ``"lost"`` when the report age exceeds the lost threshold, otherwise
        ``"active"`` for underway targets and ``"sleeping"`` for stationary
        ones. Negative ages (clock jitter ahead of the last report) count as
        fresh.
    """
    age = float(age_s)
    if not math.isfinite(float(sog_mps)) or not math.isfinite(age) or age > ais_lost_age_s(sog_mps, ais_class):
        return "lost"
    if float(sog_mps) >= AIS_ACTIVE_SOG_MPS:
        return "active"
    return "sleeping"


class AisReportClock:
    """Per-target AIS position-report clock for the display layer.

    Real AIS targets are reported on the ITU-R M.1371 cadence, not every
    simulation frame; the display age must reflect that discreteness. The
    clock emits a new report when the elapsed time since the last one reaches
    the expected interval and returns the resulting report age.
    """

    def __init__(self) -> None:
        self._last_report_s: float | None = None

    def advance(self, t_s: float, sog_mps: float, ais_class: str = "A") -> float:
        """Advances to display time ``t_s`` and returns the report age."""
        interval = ais_reporting_interval_s(sog_mps, ais_class)
        last = self._last_report_s
        if last is None or float(t_s) < last or float(t_s) - last >= interval:
            self._last_report_s = float(t_s)
        return float(t_s) - self._last_report_s

    def age(self, t_s: float) -> float:
        """Report age at ``t_s`` without emitting a new report (data gaps).

        During a historical-replay data gap no transponder report arrives, so
        the display clock must hold and the age must grow instead of resetting.
        """
        last = self._last_report_s
        if last is None:
            return 0.0
        return max(0.0, float(t_s) - last)

    def reset(self) -> None:
        self._last_report_s = None
