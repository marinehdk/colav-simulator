# P3-S4 evidence — AIS data display layer (spec #90)

Scope: backend-authoritative AIS display state (`colav_simulator/core/ais_display.py`,
additive `truth[].ais = {age_s, state}` in `gui_server/main.py`), web AIS target
layer (`web_gui/modules/ais-display.js` + 2D chart layer in
`web_gui/modules/situation-display.js` + Cesium 3D billboards in
`web_gui/modules/scene-3d.js` + AIS target card in `web_gui/app.js`/`index.html`),
self-drawn IMO SN.1/Circ.243/Rev.1 symbol assets (`web_gui/assets/ais-*.svg`).

## AIS state judgment (backend authority; thresholds)

Pure functions in `colav_simulator/core/ais_display.py`:

| state | rule | anchor |
|---|---|---|
| `lost` | `age_s > 3 × expected reporting interval` | IMO 243 §3.4 lost semantics; factor 3 = display policy (~3 missed reports). Interval per ITU-R M.1371: Class A ~0 kn → 180 s, 0–14 kn → 10 s, 14–23 kn → 6 s, >23 kn → 2 s; Class B ≤2 kn → 180 s, >2 kn → 30 s (same table as the tracker AIS sensor, `sensing.py` `AIS._measurement_rate`) |
| `active` | `sog ≥ 0.5 m/s (~1 kn)` | automated-activation policy: underway targets show the enlarged symbol + COG/SOG vector (IMO 243 §3.2) |
| `sleeping` | otherwise | stationary targets keep the small triangle, no vector (IMO 243 §3.1) |

Report discreteness: `AisReportClock` emits a new report only on the ITU
cadence, so `age_s` sawtooths instead of staying 0; historical-replay data
gaps (`historical_actor_truth.sample_kind == "inactive"`) hold the clock and
grow the age across the gap (→ `lost` after 3 expected intervals).
`dangerous` is a display-side composition (activated + existing risk rank
HIGH → bold red flashing symbol; IMO 243 §3.3) — the backend state stays
three-valued.

## Artifacts

| file | producer | content |
|---|---|---|
| `ais-four-states-2d.png` | headless Chrome over `tests/web_gui/ais-display-visual.html` (mock frames) | 2D chart with the four IMO 243 symbol states (TS1 active + vector / TS2 sleeping / TS3 dangerous, selected bracket + red label / TS4 lost ×), fused-track + radar-echo association, AIS target card (MMSI/SOG/COG/HDG/AGE/STATE/关联) |
| `ais-live-2d.png` | `tools/sango_ais_s4_probe.mjs` over the real app at :8010 (live `romsdal_busy_water_16` session) | Deployment chart with 10 backend AIS symbols (DOM markers above the vessel markers) |
| `ais-live-popover.png` | same | Chart-display popover: legend entries "AIS 目标（睡眠/激活）/ AIS 危险（红闪）/ AIS 丢失" + the `AIS 目标` layer switch (checked, coexisting with 船舶) |
| `ais-live-2d-card.png` | same (AIS symbol click) | The real `obc-poi-card` AIS target card on TS1: MMSI 101, SOG/COG/HDG, AGE 1 s, STATE 激活（矢量）, ASSOC `TS1（融合） + 雷达回波` |
| `ais-live-3d.png` | same (3D Cesium view) | Cesium chase view: teal IMO 243 billboards above the vessel models; POI card carries MMSI / AIS AGE / AIS STATE / AIS ASSOC rows alongside BRG/RNG/DCPA/TCPA |
| `ais-live-3d-card.png` | same (3D POI click) | Second frame of the 3D card with the AIS rows |
| `live-envelope-extract.json` | WS capture (`/ws/sessions/{id}`) | Ground truth: every obstacle carries `ais{age_s, state}`; ownship tracks for the association |
| `evidence-status.json` | probe | Assertion log (7/7 PASS) |

## Reproduce

```bash
# 1) web suite incl. the new tests (node 22; 460 = 447 baseline + 13)
export NVM_DIR="$HOME/.nvm" && . "$HOME/.nvm/nvm.sh" && nvm use 22
node --test tests/web_gui/*.test.mjs

# 2) backend tests (20 new in tests/test_ais_display.py)
.venv/bin/python -m pytest tests/test_ais_display.py -q

# 3) four-states harness screenshot (repo-root static server; CDP capture)
python3 -m http.server 8031 --bind 127.0.0.1 &
node tools/sango_ais_s4_probe.mjs   # live :8010 evidence (session + Chrome CDP, self-cleaning)
# (the harness shot itself rides the probe pattern; one-off:
#  headless Chrome → http://127.0.0.1:8031/tests/web_gui/ais-display-visual.html →
#  Page.captureScreenshot at deviceScaleFactor 2, window 940x760)

# 4) backend reload before the live probe (launchd serves :8010)
launchctl kickstart -k gui/$(id -u)/com.marine.colav-simulator.frontend   # + ~60 s prewarm
```

## Notes

- Historical AIS workbench (`historical-ais-*.js`) untouched; its tests ride
  the full web suite. `tests/test_historical_ais_scene_guard.py` (2 byte-stability
  guards) fails identically on clean HEAD — pre-existing local dataset-state
  artifact, not from this stage.
- Unity/sango untouched → EditMode suite not re-run (last known 506/506).
