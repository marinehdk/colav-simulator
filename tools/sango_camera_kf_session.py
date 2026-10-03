#!/usr/bin/env python3
"""Camera-only KF diagnostic session launcher (P1-1a E2E, spec #90 review fix).

The product session API intentionally refuses everything outside the published
tracker surface (god | vimmjipda), so a live camera-only KF session — the
causal E2E leg for the ``external_cameras:`` assembly — cannot be created
through POST /api/sessions. This launcher seeds it directly through the
runner's internal builder (``_prepare`` + ``manager._activate``) and serves the
STANDARD gui_server app on a private port; every route the probe consumes
(observations POST/status, confirmed-tracks, session start, WS) is the real
backend surface, and the session itself is the real simulator chain
(scenario_default -> scene-built KF iterating the assembled sensor list).

Diagnostic-only bypass: the product capability gates stay untouched; the
requested tuple (rule14 / head_on_camera / nominal / scenario_default) is a
sanctioned diagnostic combination in spirit (nominal = no COLAV, straight LOS
approach — the target actually reaches YOLO detection range, unlike a vo run
that keeps 300 m+ standoff).

Usage: .venv/bin/python tools/sango_camera_kf_session.py --port 8011
"""

from __future__ import annotations

import argparse
import os


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument("--scenario-id", default="head_on_camera")
    args = parser.parse_args()

    # The launcher must not inherit the desktop prewarm (Historical AIS ENC
    # preload is pointless for this diagnostic and slows startup).
    os.environ.pop("COLAV_HAIS_PREWARM_ON_STARTUP", None)

    import uvicorn

    from colav_simulator.experiment.contracts import RunSpec
    from gui_server.main import app, manager

    spec = RunSpec(
        scenario_id=args.scenario_id,
        validation_rule_id="rule14",
        algorithm_id="nominal",
        tracker_id="scenario_default",  # scene-built tracker: kf + assembled sensors
        strict_no_fallback=True,
        # The nominal head-on pair passes at sub-metre clearance; termination
        # would kill the session before the target reaches YOLO detection range.
        # The E2E window needs the pass-through approach alive.
        terminate_on_collision_or_grounding=False,
    )
    prepared = manager.runner._prepare(  # noqa: SLF001 - deliberate diagnostic bypass
        spec, capability_profile_id="diagnostic_camera_kf_e2e"
    )
    manager._activate(prepared, record_replay_trace=False)  # noqa: SLF001
    session_id = manager.session_id
    print(f"[camera-kf-session] diagnostic session seeded: {session_id}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
