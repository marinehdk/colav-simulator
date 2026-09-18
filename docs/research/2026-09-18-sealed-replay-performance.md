# Sealed replay 5× playback stalls — 2026-09-18

## Reproduction and cause

Run `273b0bf2-1f33-42ab-b84d-9e7918b706e6`, Three-Ship / Mid-MPC / Original GNC. The reported stalls near 8.0 and 32.4 seconds match exhaustion of the initial 8-second window and the subsequent approximately 24-second window (240 frames at 10 Hz).

The replay path reads recorded evidence; it never executes MPC or advances a live session. Three costs combined:

1. The trace is approximately 2 GiB uncompressed, above the reader's 512 MiB decoded-memory cache. Previously this disabled indexed decoded storage. Each requested frame reopened the gzip and decompressed again from the beginning; later windows made this worse.
2. A 24-second window contains 93,373,866 bytes of complete diagnostics. Generic FastAPI JSON processing/serialization added work before sending this uncompressed body.
3. The frontend fetched only after exhausting its current window, held its presentation clock, and retained a misleading PLAYING label while waiting.

Red reproduction: `.venv/bin/python tmp/replay_perf_20260918/check_window.py` reported **19.4537 seconds** for the 8–32 second window and failed its **4.8-second** consumption budget at 5×. An earlier curl measured 17.1547 seconds. The minimized large-trace regression reopened gzip 13 times where one decoded seek index was required. The new frontend test failed because no request was issued before window exhaustion.

## Fix

- Keep small decoded traces in memory; spill large ones to an anonymous temporary file and read-only mmap. Decode in bounded chunks, retain indexed reads, and release the derived storage with the reader. Original artifacts remain unchanged. Unavailable cache storage retains the existing streaming read path.
- Serialize recorded windows directly with orjson and negotiate lossless gzip level 1. Preserve every JSON field, frame, predecessor/successor, history point and canonical threat projection.
- Start with up to 24 seconds of evidence, bounded by the same 240-frame budget; an 8-second initial window is only 1.6 wall seconds at 5× and occasionally underruns. Prefetch one bounded next window immediately while continuing to render the current one. Replace it only when the playhead enters the next window. Keep requests generation-bound across seeks/run changes.
- Explicit BUFFERING when evidence has not arrived; hold the clock across rate changes and pause/resume. Never extrapolate missing evidence.

No planner, GNC, safety gate, trace capture budget, or evidence trust boundary changes.

## Measurements and checks

| Measurement | Before | After |
|---|---:|---:|
| Warm 8–32 s window | 19.45 s | 1.32 s |
| Wire bytes, same window | 93,373,866 | 23,723,624 |
| Warm 600–624 s window | — | 1.60 s |
| First cold read including validation/index preparation | — | 35.45 s |

After measurements above use an isolated read-only replay API on 8015. The first open still prepares and validates the full recorded trace before playback; it is distinct from steady playback throughput. The test server was stopped after measurement.

The complete JSON returned by the old 8010 endpoint and the new endpoint for 8–32 s compares equal, including recorded diagnostics and canonical threat documents. Compression is not diagnostic pruning or frame downsampling.

Final backend related regression: **99 passed** (includes the new large-trace and gzip parity tests). Frontend replay host, source, clock and catalog: 77 passed. The obsolete assertion forbidding the user-requested actual-speed element was narrowed to forbid only the redundant requested-rate label.

## Acceptance boundary

This run contains only the trusted recorded prefix through **652.5 seconds** (6,526 frames), despite live execution completing around 1,745 seconds. INCOMPLETE is due to the existing 2 GiB capture limit. Playback must stop at that trusted boundary; this fix does not invent the unrecorded suffix or change the independent evaluation result.

## Browser and deployment acceptance

8010 restarted with the final backend, PID **61948**, after verifying the prior active session was FINISHED. Existing Historical AIS ENC startup prewarm took 100.1 seconds. HTTP 200 verified. Final frontend uses `evaluation-replay.js?v=20260918-replay-prefetch-v3`; the subsequent frontend refinements required reload only.

The real in-app browser replayed **0–652.5 s at requested 5×**, reached `REPLAY ENDED`, and displayed source frame **6526**. Measured progression between the first and last PLAYING samples: **4.99950×**. End was observed 131.407 seconds after initiating the Play click, including click/observation latency. **174 DOM samples**, zero BUFFERING samples, including samples spanning the original 8.0/32.4-second boundaries. This is sampled UI evidence, not a claim of zero sub-sample scheduling jitter.

The earlier half-window-prefetch candidate completed at approximately 4.96× with a brief buffer near 488 s; a later pass exposed the initial 8-second underrun. Both motivated the final full-window prefetch lead and larger initial reserve. Final evidence: `evidence/sealed-replay-performance-20260918/browser-playback-final.json`. Earlier measurement retained separately as `browser-playback.json`.

After ending, seeking backward to 0 seconds restored source frame 1; playback resumed and passed 64 seconds before being paused. Browser console errors: none. The delivered browser tab is paused at approximately 65.2 seconds.

Original HTTP reproduction on deployed 8010 now passes: **1.28135 s** for the same **93,373,866-byte uncompressed** JSON (no compression requested), against the 4.8-second gate.

Prevention: performance acceptance must include traces above the cache threshold, realistic diagnostic payload sizes, and continuous playback across multiple window boundaries. Test frame count alone does not cover byte-volume scaling. Existing injected clock/fetch seams support these regressions; no controller redesign is required.
