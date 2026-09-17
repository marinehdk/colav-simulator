# Prototype verdict

Date: 2026-09-17

**Answered: yes — an existing Colav recording can drive a real Unity scene through Gemini's original external-pose service, with pause, seek, speed changes and actual-transform readback.**

## What ran

- Unity Editor 2019.4.20f1 and a built standalone macOS player, Intel binaries through Rosetta on Apple M3.
- Actual `GeminiOSPInterface.Simulation/DoStep` RPC, delegated to unchanged upstream `SimulationServiceImpl` and `ThreadManager`; nine original source files hash-checked.
- Recorded VO overtaking run `3f99134e-070a-4389-adee-03b91979c8df`: 1,571 samples, 0–785 s, 44.1 m ownship plus one target.
- Original recorded ENC texture and environment telemetry; procedural display hulls, nominal route and historical trajectory lines.

## Manual execution evidence

- Both Editor and standalone player accepted real RPCs and returned actual Unity-transform receipts.
- Forward/backward seeks checked at 0, 32, 270.5, 360, 785 and back to 0 seconds.
- Maximum absolute north/east coordinate-component difference between original JSON doubles and Unity readback: **0.0001212554 m**. This measures transport/coordinate conversion only, not model accuracy.
- 16× playback advanced to 16.0 recorded seconds in the one-second observation; after pause, recorded time and vessel positions stayed unchanged across subsequent checks. This is functional evidence, not a hard-real-time benchmark.
- `evidence/player-verification.json` retains checkpoint receipts and the pause observation.
- `evidence/delivery-receipt.json` is the latest delivery snapshot. `evidence/unity-player.png` is a real screenshot captured by Unity, not an image-generated mockup.
- `evidence/build-summary.txt` records the successful standalone build marker. Full local diagnostic logs remain under ignored `outputs/`.

No test suite was added: this was the explicitly requested throwaway prototype. Validation used actual playback actions, transform readback, build output and visual inspection.

## Adjustments needed to run the archived baseline

1. Installed Unity Hub and the pinned legacy Editor; user signed in, Personal activation was verified in Hub.
2. Used only the upstream pose-service dependency closure, avoiding restricted NTNU scene/model packages and unrelated sensor-rendering dependencies.
3. Downloaded the gRPC Unity package from Gemini's own setup guide, checked its SHA-256, excluded the conflicting macOS i386 plugin from a 64-bit build.
4. Included dynamically loaded shaders/materials explicitly in the player build.
5. Isolated the launcher, background process logs and loopback controls; periodic paused-pose refresh lets the client detect/reconnect to a restarted Unity process.

## Bounds and next decision

This fulfills the requested **recorded-scenario MVP slice**, not all Step 1 acceptance gates. It does not execute a new avoidance solve, simulate validated physical waves, run Gemini camera/radar/lidar models, implement production L1, or demonstrate real-vessel synchronization. Recorded tracker `god` is idealized L1. Hull shapes and wave ripples are explicitly illustrative; displayed dimensions can be magnified without altering pose distances.

The useful architectural decision is to retain separate ownership of recorded/simulated state and Unity rendering. A production adapter should additionally define vessel IDs, timestamps, reset/cancellation, high-rate acknowledgements and bounded failure behavior; Gemini's original blocking pose service is retained here as research evidence, not promoted as production middleware.

Captured on `codex/prototype-digital-twin-replay`; main is unchanged. No implementation issue was supplied. Use this branch/commit as the source pointer when opening the subsequent integration issue. No production code promotion is implied.
