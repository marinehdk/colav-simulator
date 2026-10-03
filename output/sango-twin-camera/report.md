# P1-1a E2E — camera-only KF causal probe (sango_twin_camera_probe)

- date: 2026-10-03T16:55:25.987Z
- session: `f13714be-3370-43c2-8519-fff4fde362db` (rule14/head_on_camera/nominal/scenario_default — scene-built KF, external_cameras the ONLY sensor)
- backend: diagnostic launcher on 8011 (product surface untouched); feed: replay of the composed frame
  (real twin render + target at its georef-projected box) through the REAL YOLO service and observations endpoint.
  Twin render gap (no target vessel ahead of ownship in live mode) ledgered in review-residue.md.

## Causal pair

- LEG ON: camera-source confirmed track existence=0.9994519603984 sources=[{"sensor_id":2,"last_seen_age_s":0}]
- LEG OFF: replay killed -> track decayed out of the confirmed product: true; accepted_frames 10 -> 10 (frozen)

## Assertions

- PASS  launchd twin-player downed for probe (single-instance) — gui/502/com.marine.colav-simulator.twin-player
- PASS  feed canvas artifact present (real twin render) — /Users/marine/Code/Colav-Simulator/output/sango-twin-camera/feed-frame.jpg
- PASS  boat crop artifact present (YOLO-verified repo paper figure) — /Users/marine/Code/Colav-Simulator/output/sango-twin-camera/boat-crop.png
- PASS  composed frame built (target at georef-projected pixel box) — /Users/marine/Code/Colav-Simulator/output/sango-twin-camera/composed-frame.jpg
- PASS  diagnostic camera-kf backend up (8011, standard app surface) — /tmp/sango-camera-kf-session.log
- PASS  camera-only kf session seeded (scenario_default -> scene-built KF) — session=f13714be-3370-43c2-8519-fff4fde362db
- PASS  request identity is scenario_default (scene-built tracker: kf + assembled sensors) — spec.tracker_id=scenario_default
- PASS  session started — session=f13714be-3370-43c2-8519-fff4fde362db
- PASS  replay feeder publishing on the FramePublisher endpoint — seq=0
- PASS  YOLO detector up (CPU) with forward branch -> 8011 observations — /tmp/sango-camera-detector.log
- PASS  LEG ON: observations accepted (composed frame -> real YOLO -> POST -> backend) — [{"sensor_id":2,"mount_id":"mast_ptz_eo","frames":5,"detections":5,"last_frame_seq":14}]
- PASS  LEG ON: confirmed-tracks carries the camera-source track (sensor_id=2 in sources[]) — existence=0.9994519603984 sources=[{"sensor_id":2,"last_seen_age_s":0}]
- PASS  LEG ON: track sources stay camera_eo (2), not a synthetic radar fill — [{"sensor_id":2,"last_seen_age_s":0}]
- PASS  LEG OFF: replay feed killed — accepted_frames at kill=10
- PASS  LEG OFF: camera-sourced track vanished from confirmed-tracks (existence decay, no feed)
- PASS  LEG OFF: observations accepted_frames frozen (no feed -> no new georef records) — at kill=10 after=10
