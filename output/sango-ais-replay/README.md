# P3-9 evidence — Evaluation Replay AIS backfill (spec #91 batch-2b)

Scope: the sealed-trajectory replayer (`web_gui/modules/replay-source.js`) now
projects the additive AIS display field `truth[].ais = {age_s, state}` on
obstacles, so the existing AIS layers (2D chart in `situation-display.js`,
Cesium billboards in `scene-3d.js`, target card in `scene-target.js`) work in
the Evaluation > Replay view exactly as they do live. No backend change: the
replay side rebuilds the report age on the web with the M.1371 mirror of
`colav_simulator/core/ais_display.py` (`aisReportingIntervalS` /
`aisTargetState` / `replayAisReportAge` — same constants, same clock walk as
`gui_server/main.py::_record_ais_reports`; backend stays the authority).

Rebuilt-clock semantics (deterministic in the playhead = the replay display
clock, hence seek/rate/pause safe):

- reports emit on the ITU-R M.1371 autonomous cadence per recorded SOG
  (Class A ~0 kn → 180 s, 0–14 kn → 10 s, 14–23 kn → 6 s, >23 kn → 2 s);
- `historical_actor_truth.sample_kind == "inactive"` frames emit no report —
  the age grows across the data gap (→ `lost` after 3 expected intervals);
- state = `lost` beyond 3×interval, else `active` at SOG ≥ 0.5 m/s, else
  `sleeping`; judged at the displayed (interpolated) SOG;
- data boundary: the replay window `history` strip is position-only (no SOG,
  no sample kind — `TraceBundle.position_history`), so the rebuilt clock
  starts at the first full frame at/before the playhead; ages near a window
  start read as a fresh report. Same bounded-window behavior as the live page.

## Artifacts

| file | producer | content |
|---|---|---|
| `ais-replay-2d.png` | headless Chrome over `tests/web_gui/ais-replay-visual.html` (sealed mock frames, playhead 44 s) | 2D replay chart: TS1 active (teal triangle + vector), TS2 moored sleeping (0 kn → 180 s cadence, AGE 44.0 s), TS3 lost × after the recorded silence (AGE 34.0 s > 30 s); HUD table carries the rebuilt {MMSI, SOG, AGE, STATE} straight from `projectReplayFrame` |
| `ais-replay-card.png` | same, `?card=1` | AIS target card on TS1: MMSI 257041500, AGE 4.0 s, SOG 5.0 kn, STATE 激活（矢量）, 关联 独立目标 |
| `ais-replay-seek.png` | same, `?card=1&t=20` | the SAME evidence seeked back to t=20 s: TS1 AGE 0.0 s (fresh report on the 10 s cadence), TS2 20.0 s, TS3 back to 激活 at 10.0 s — the rebuilt age is a pure function of the playhead |
| `evidence-status.json` | manual ledger | acceptance facts + where each comes from |

Mock scene (all AIS values projected by `replay-source.js`, none hand-labelled):
sealed window 0–44 s at 2 s cadence; TS1 ~5 kn underway, TS2 moored 0 kn,
TS3 ~6 kn until a recorded `sample_kind: "inactive"` gap from t=10 s.

## Data boundary of this evidence

Mock frames — the parallel batch owns the backend/live probes, so no real run
was replayed here. The window frames carry the same fields a real run's
`frames.jsonl` carries per ship (`id`, `mmsi`, `state`, `csog_state`,
`historical_actor_truth.sample_kind`), and the projection path is the
production one (`projectReplayFrame` → telemetry-projection →
situation-display). Static context ships (`{id, mmsi}`) are not the AIS data
source — per-frame SOG/kind drive the rebuilt clock; `ais_class` is the
backend default `"A"` (the live path never sets another class either).

## Reproduce

```bash
# 1) web suite incl. the new tests (node 22; 487 = 478 baseline + 1 guard + 8 replay-AIS)
export NVM_DIR="$HOME/.nvm" && . "$HOME/.nvm/nvm.sh" && nvm use 22
node --test tests/web_gui/*.test.mjs

# 2) replay-AIS unit tests alone (rhythm table / gap semantics / envelope projection / seek)
node --test tests/web_gui/replay-source.test.mjs

# 3) specifier uniqueness guard (P3-6 generalization)
node --test tests/web_gui/module-specifier-uniqueness.test.mjs

# 4) screenshots (repo-root static server + one-off headless Chrome, S4 pattern)
python3 -m http.server 8041 --bind 127.0.0.1 &
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$C" --headless=new --disable-gpu --hide-scrollbars --window-size=940,760 \
  --force-device-scale-factor=2 --virtual-time-budget=12000 \
  --screenshot=output/sango-ais-replay/ais-replay-2d.png \
  "http://127.0.0.1:8041/tests/web_gui/ais-replay-visual.html"
"$C" ... --screenshot=output/sango-ais-replay/ais-replay-card.png \
  "http://127.0.0.1:8041/tests/web_gui/ais-replay-visual.html?card=1"
"$C" ... --screenshot=output/sango-ais-replay/ais-replay-seek.png \
  "http://127.0.0.1:8041/tests/web_gui/ais-replay-visual.html?card=1&t=20"
```

Harness: `tests/web_gui/ais-replay-visual.html` — seek buttons (±2 s/±10 s),
play/pause and 0.5–20× rate buttons drive the replay clock; ages must follow
sim time only (rate changes how fast the playhead moves, never the age).
