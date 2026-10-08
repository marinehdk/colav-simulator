# X-band radar implementation and local acceptance — 2026-10-08

## User decisions

- SENSOR RADAR is replaced by PPI; the bottom toolbar contains view controls, including DT, without PPI.
- Title is X-BAND RADAR and inherits SPEED card typography. Range selectors sit below the image and include NM.
- Select the hardware anchor from NTNU milliAmpere1/2: Simrad HALO24, based on the 2025 vessel papers and manufacturer specifications. Earlier milliAmpere1 hardware model remains unspecified.
- Radar video/CFAR run in SHADOW. Existing production tracker/planner inputs stay on the legacy point-measurement path pending separate qualification.
- Commit this conversation's changes to local main only. GitHub publication requires later user acceptance.

## Implementation status

| Phase | Delivered | Acceptance boundary |
|---|---|---|
| P0 | Immutable scan evidence, shared same-time sampling for tracker/SFD/PPI, explicit sensor identity, no browser-generated radar clutter, recorded scan hashes | Seeded legacy measurement hashes unchanged at sea states 0/3/6 |
| P1 | HALO24-anchored 2048×1024 statistical video, addressed random field, aspect/scatter-center echoes, beam/range PSF, sea/rain effects, ENC landmask or configured DEM, range CA-CFAR | Shadow channel only; engineering RCS/range PSF/clutter/receiver model, not proprietary HALO firmware or Doppler/IQ emulation |
| P2 | Deflate binary spokes, bounded checkpoint cache, nested replay block deduplication, sealed-window checkpoint sharing, recorded replay recovery, NU/HU/CU, relative/true motion, spoke-origin translation, gain/sea/rain display filters, echo trails, VRM/EBL, separate CFAR/production tracks/AIS overlays | Display range controls crop the physical scan; hardware range/rpm remains the scenario setting. Attitude/mount offsets are configured priors; the ship runtime remains planar |
| P3 | Manufacturer profile anchor, normalized recording verification, byte/shape/hash guards, external-reference bias estimation, explicit synthetic/measured provenance, CLI tools | REAL HALO24 DATA CALIBRATION NOT COMPLETE: no NTNU raw spokes, PCAP, surveyed references or measured antenna phase-center data available |

P0 production point measurements and P1 shadow video are distinct evidence streams. Production fusion does not consume the shadow CFAR output. AIS overlays use actual simulated AIS measurement reports with acquisition timestamps; they do not substitute vessel truth positions for radar detections.

## Validation

- Node v22.22.3: `node --test tests/web_gui/*.test.mjs` — 489 passed, 0 failed.
- Python focused radar/fusion/capture/replay suite — 154 passed, 0 failed. Exact command below; output archived in `2026-10-08-radar-evidence/backend-tests.log`.
- Original RadarXBand seed 731, 81 samples × three sea states: byte-level measurement hashes remain identical with added SFD and display consumers.
- CA-CFAR homogeneous exponential-noise false alarms checked against a five-standard-deviation binomial bound; high-power point detection, tick-partition invariance, CRC/length rejection, zero-spoke initialization, ENC registration, nested checkpoint decode, reference-bias wrap and synthetic calibration boundary covered.
- Synthetic qualification: 51 frames; P50 8.81 ms, P95 29.01 ms per scan generation plus packet projection, on this host with one target and a 3 NM physical range. This is a focused benchmark, not an all-scenario or whole-system latency claim.
- Calibration CLI inspect/fit both executed; output remains `SYNTHETIC_ONLY_REAL_CALIBRATION_PENDING`. Bias fixture has known +8 m / +2° errors and is an estimator test, not real calibration.
- Browser: title and SPEED computed font family/size/weight/color/spacing match; range selectors below canvas; control region inside card; backend video decoder reaches SHADOW with content-hashed checkpoint; HU and CFAR toggles work on the paused live session.
- 8010 frontend was reloaded and the original Run Specification restored with exact dictionary equality (including original GNC stack), then stepped to 3.0 s and left PAUSED for user testing. Live evidence reports radar_scans=1, SHADOW, ENC_LANDMASK and executed_tracker=vimmjipda. No claim of full COLAV safety qualification from these steps.
- New/changed radar modules pass Ruff. Existing baseline lint findings in sensing.py (3) and gui_server/main.py (5) are retained; no unrelated formatting repair.
- Unity sources/player and twin auto-start policy unchanged. No GitHub push, external-repo push, planner threshold change, or full Mid-MPC acceptance claim.

### Commands

```sh
.venv/bin/python -m pytest -q tests/test_radar_scan.py tests/test_radar_video.py tests/test_radar_transport.py tests/test_radar_xband.py tests/test_vimmjipda_multisource.py tests/test_chart_replay_capture.py tests/test_replay_capture.py tests/test_replay_window.py tests/test_replay_api.py
node --test tests/web_gui/*.test.mjs
.venv/bin/python tools/radar_calibrate.py inspect recording.jsonl --output inspection.json
.venv/bin/python tools/radar_calibrate.py fit references.json --output bias.json
```

## P3 input formats

Recording JSONL first line:

```json
{"schema_version":"radar-calibration-input@1","source_kind":"measured","profile_id":"simrad_halo24_milliampere_v1","provenance":{"dataset_id":"REPLACE","source_uri":"REPLACE","decoder":"REPLACE"}}
```

Subsequent lines contain strictly increasing `t_s` and `shadow_video.chunk/checkpoint` documents using `deflate-base64-u8`, explicit shape and uncompressed SHA-256. Vendor PCAP needs its documented decoder before normalization; the tool does not guess a proprietary layout. A measured declaration alone is not trusted ground truth and yields MEASURED_DATA_REVIEW_REQUIRED.

Reference input:

```json
{"source_kind":"measured","provenance":{"reference_method":"surveyed reflector positions","uncertainty":"REPLACE"},"pairs":[{"range_m":508,"bearing_deg":1,"reference_range_m":500,"reference_bearing_deg":359}]}
```

At least five finite paired references are required. Returned range/bearing biases are reviewable estimates; no runtime settings are applied automatically. Truth identity annotations belong only to this offline audit input, not runtime detections.

## Remaining acceptance

- Obtain real HALO24 data and surveyed references; determine actual phase-center height, range-mode/rpm policy, range PSF and sea/rain statistics.
- Independently qualify shadow detections/fusion before switching the production measurement path.
- Manual UI review and longer live/replay stress runs; full simulator/MASS-L3/COLAV safety qualification remains separate.
- Inspect local main changes and accept before publishing to GitHub.
