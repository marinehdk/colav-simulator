# Gemini / Unity × Colav-Simulator — PROTOTYPE

Question: can an existing Colav run drive a real Gemini/Unity scene with reliable pause, seek and playback, without changing the recorded trajectory?

This is a disposable **playback/integration prototype**, not a production UI or algorithm acceptance campaign. User selected Gemini/Unity explicitly; no Three.js/PyGemini renderer is used.

## Run

On the prepared machine, double-click `Start Gemini Replay.command`, or:

```sh
python3 examples/prototypes/gemini-replay/run.py
```

Unity shows the 3D scene. `http://127.0.0.1:8127` is a local playback control panel, not a replacement renderer. Unity menu `COLAV → Play Gemini Replay` can also start the scene. Pause/seek, 1/8/16/32× speeds, three camera views and actual-size display are available. Right drag rotates; wheel zooms.

On a fresh checkout:

```sh
cd examples/prototypes/gemini-replay
python3 -m venv .build/venv
.build/venv/bin/pip install -r requirements.txt
.build/venv/bin/python prepare.py
# Install and activate Unity Editor 2019.4.20f1 (Intel), then:
.build/venv/bin/python run.py
```

## Actual integration path

`data/replay.json → Python gRPC client → GeminiOSPInterface.Simulation/DoStep → unchanged Gemini SimulationServiceImpl → unchanged ThreadManager → Unity Transform → readback receipt`

Gemini commit: `ce538dff7e1a8d1f1a249d7eeed2f5349fdf1b33`. Nine upstream C# files are copied unchanged and hashed in `upstream-lock.json`, including the actual pose-service implementation and its dependencies. Our subclass adds count validation and reads back transforms **after** the original service applies a request; it does not implement an alternative pose application path.

The upstream `SimulationController` is included as a compile dependency; the prototype bootstrap hosts the original service directly. This avoids dependence on restricted prefabs while keeping the real implementation in execution. The sensor base/protobuf files are dependencies, not evidence of running camera/lidar/radar simulation.

Only local north/east and heading are supported by this Gemini proto. Local north/east are metres; heading converts recorded radians to degrees. Unity mapping is `(x=east, y=0, z=north)`, yaw clockwise from north. No Rigidbody/physics integration drives these vessels. Roll/environment/actuator values remain recorded telemetry, not additional inferred motion.

## Data and bounds

- Source run: `3f99134e-070a-4389-adee-03b91979c8df`, source commit `b2348cb5f9f000d62b665bef73bc737acaf3d9e7`.
- VO overtaking, original GNC environment-on, 785 seconds, 1,571 recorded samples, one ownship and one target.
- Saved display dimensions: 44.1 × 8 m ownship; 8.45 × 2.71 m target. Default visual hull magnification is labelled ×3; pose distances stay true. Toggle to actual size.
- Tracker is `god`: idealized L1 situation input, not validated sensor fusion.
- Geometry is a procedural prototype; the flat ENC image comes from the recorded run. No licensed Trondheim or NTNU vessel assets are claimed or included.
- Ripples are visual only, tied to replay time; no wave-force or sensor-fidelity claim.
- Full trajectory lines are historical reference, not live forecasts. Discrete protocol fields use the latest recorded sample at/before requested time. Fast playback may skip display samples; it never reruns the solver or changes stored data.
- `FINISHED` and saved evaluation fields describe the original recording only; playback success is not full Step 1 physics/algorithm acceptance.

`data/provenance.json` contains original artifact SHA-256 values. `export_replay.py` reproduces the export from the source run using the existing project Python environment.

## Evidence

Runtime receipt: `outputs/pose-readback.json` contains actual Unity positions/headings and error versus each submitted protobuf request. Screenshot: `outputs/unity-replay.png`, captured inside Unity. Both are absent until real execution; no simulated/fake server is used as acceptance evidence.

Current implementation and runtime verification status are recorded in `VERDICT.md`. The prototype lives on `codex/prototype-digital-twin-replay`, separate from main. No implementation issue was supplied; the commit and this folder are the context pointer pending a chosen production integration issue. No production promotion has been validated.

## Sources / dependencies

- [Gemini source](https://github.com/Gemini-team/Gemini/tree/ce538dff7e1a8d1f1a249d7eeed2f5349fdf1b33), MIT license retained in `unity/Assets/GeminiOriginal/LICENSE.txt`.
- [Gemini original setup guide](https://github.com/Gemini-team/Gemini/blob/ce538dff7e1a8d1f1a249d7eeed2f5349fdf1b33/docs/index.md), including official gRPC Unity package. Download hash is pinned; binary plugins are not committed.
- [Unity licensing](https://docs.unity.com/en-us/hub/manage-license), [Hub CLI](https://docs.unity.com/en-us/hub/use-hub-cli).
