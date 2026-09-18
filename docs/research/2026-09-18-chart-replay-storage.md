# Complete Mid-MPC / Three-Ship chart replay storage

## Scope and format

Product capture now uses `colav.decision-replay.v2`, profile `colav.chart-replay.v1`. Full audit capture remains available through the unchanged default `TraceSinkPolicy(capture_profile="full")` and debug recorder. Existing v1 replay files remain readable.

Every source frame retains its sequence/time, all ships' position, attitude, velocity, turn rate, active state, waypoints, execution references, measurements, track IDs/generations/estimates/covariances, and historical actor display facts. Mid-MPC's entire typed `prediction_render` document is preserved, including current/previous/rejected predictions, target predictions, quality and execution authority. The original canonical threat snapshot is retained without recomputing COLREG or risk. ENC geometry/image remains in the Run's static context.

Unrelated GNC internals, balance diagnostics, duplicate generic prediction arrays (when the typed render document is present), solver assembly, receipts and per-frame evidence timelines are omitted from chart capture. Other algorithms retain their legacy prediction/detail paths. Planner event identity/order/status remain recorded; only the embedded repeated full planner dump is reduced to its recorded summary. Collision, grounding, risk, lifecycle and mission events are not filtered out.

Large immutable display blocks are written once with a SHA-256-derived reference; definitions accompany the first referencing frame. Subsequent frames keep their own motion data and references. Missing blocks/redefinitions fail validation; incomplete queues/budgets still fail closed. A sealed digest covers definitions and references together. Readers expand independent objects so consumer mutations cannot corrupt cached blocks. The descriptor reports chart capture and disables full raw-frame/planner-detail claims. No position rounding, frame thinning, predicted-path smoothing or algorithm changes.

## Full recorded source and conversion

The previously validated complete real-GNC Run `74e2fa1e-2150-4bc7-b0b8-5137073de0fd` was available in the performance worktree. It was copied/imported through the new capture writer into the main runs directory with the same Run identity and unchanged audit artifacts. This is a storage conversion of recorded evidence, not a newly executed simulation. The original full source is untouched. The truncated `273b0bf2` was not used to invent missing frames.

`tools/compact_replay.py SOURCE --output-root runs` refuses an existing destination or incomplete source, verifies the original digest, uses the normal 2 GiB capture budget, and compares the complete per-frame chart semantic digest after disk round-trip before publishing the imported Run.

- **17,450 frames**, **0–1744.9 s** (simulation completion at approximately 1745 s).
- Old capture bytes: **5,377,842,722**; new: **121,156,056**.
- Old `frames.jsonl.gz`: **1,184,712,672 bytes**; new: **12,263,423 bytes** (about **99% smaller**).
- New recording state: **READY**, no truncation, no capacity override.
- All-frame chart semantic SHA-256: `74f476071f8ce5f7c1b6db2013592ecaf3cc477794d939736b17a62e60b9260b`.

These sizes refer to the replay capture, not the separate trajectory/GNC/planner audit artifacts, which remain unchanged.

## Verification

- Round-trip verified every retained field of all 17,450 frames, including each full prediction document and canonical threat block. Final decoder independently rechecked the same hash.
- Four real frames spanning startup, SOLVE and HOLD were run through the actual frontend replay-source and telemetry projection: plans/chart layers, motion, navigation, sensors, threats, references and prediction geometry compare equal to the original.
- Reader/API/format suite: 92 passed. Product capture/live serialization: 27 passed. Additional replay playback/evidence/event suites are recorded with final validation below; these suites overlap and must not be summed as unique tests.
- Missing reference, changed prediction, repeated prediction, random seek and detached return-value regressions included. Corrupt/non-object index behavior remains typed INCOMPLETE.

## Browser acceptance and deployment

8010 serves the new capture/reader code, HTTP 200. The prior unstarted Three-Ship configuration was saved and restored field-for-field as CREATED session `dd3d3977-e8b4-4208-ad0b-e74c2bd03aca`; no simulation was started or replaced during the replay acceptance.

The browser opened Run **74e2fa1e** through Evaluation → Replay, selected **5×**, and played from zero through **1744.9 seconds**, including the old 652.5-second cutoff and 1500 seconds. It ended normally with **source frame #17450**. Measured progression between PLAYING samples was **5.00030×**; **351 DOM samples**, zero BUFFERING samples. Completion was observed at wall 353.066 seconds, including click latency and observation gaps; this is not a precise timestamp of the last render. No browser console errors. A chart screenshot during playback showed all vessels and the retained prediction/route layers. The delivered tab remains at the completed replay.

Evidence: `evidence/chart-replay-storage-20260918/browser-playback.json`, `descriptor.json`, and `compaction.json`. Descriptor confirms READY, 17,450 trusted frames, no truncation, v2 chart profile, seekable, and no full raw-planner detail claim.

Final non-overlapping backend suites: **129 passed** (92 reader/API/format + 27 capture/serialization + 10 playback/evidence/events). Ruff and diff checks passed. Original files and audit artifacts remain available; no raw safety evidence was overwritten or newly fabricated. New product recordings default to the compact chart profile.
