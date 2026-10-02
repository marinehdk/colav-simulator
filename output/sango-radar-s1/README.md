# P3-S1 evidence — X-band radar model + web PPI panel (spec #90)

Scope: `RadarXBand` backend sensor model (`colav_simulator/core/sensing.py`),
terrain occlusion (`colav_simulator/core/radar_occlusion.py`), additive
`radar_ppi` envelope descriptor (`gui_server/main.py`), web PPI panel
(`web_gui/modules/radar-ppi.js` + deployment display-bar "PPI" toggle).

## Artifacts

| file | producer | content |
|---|---|---|
| `pd-range-curve.json` | `tests/test_radar_xband.py::TestPdModel::test_pd_range_curve_evidence` | SNR(r) + analytic/Monte-Carlo PD per range (400 revolutions per point, seed 99). Detection cliff between 3-6 nm for a 20 m2 boat — consistent with milliampere-ch5 §4.3 "消费级圆顶对玻璃钢艇 2-6 nm 实效". |
| `clutter-statistics.json` | `tests/test_radar_xband.py::TestClutter::test_poisson_statistics_and_radial_decay` | Poisson cardinality mean/variance vs analytic annulus integral (rate 5e-7/m2, decay 2, Beaufort 3), blind-ring exclusion, near-range dominance. |
| `occlusion-cases.json` | `tests/test_radar_xband.py::TestTerrainOcclusion::test_occlusion_case_evidence` | Synthetic 40 m ridge DEM: blocked / clear / tall-target-over-ridge LOS cases. |
| `real-dem-occlusion.json` | run against `tmp/m6-spike-data/straits_clamped.tif` (M6 strait DEM, GEBCO+GLO-30, EPSG:32648, downsample 4) | Real-terrain cases: open-water clear line, island-shadowed water endpoint (blocked), land endpoint (blocked). |
| `ppi-panel.png` | headless Chrome over `tests/web_gui/radar-ppi-visual.html` | PPI panel render: range rings/ticks, rotating sweep with afterglow, deterministic clutter speckle, target blips (brightness = shared SNR proxy), ownship marker, range-scale buttons 0.75/1.5/3/6/12/24 nm. |
| `app-8010-boot.png` | headless Chrome over `http://127.0.0.1:8010/` | Real web app boot with the PPI changes loaded (zero regression; Deployment display bar carries the new `PPI` button — see `tests/web_gui/radar-ppi.test.mjs` shell-integration test). |

## Reproduce

```bash
# backend model + artifacts (tests write the JSONs)
.venv/bin/python -m pytest tests/test_radar_xband.py -q

# real-strait-DEM occlusion check (DEM is local scratch data, not in git)
.venv/bin/python - <<'PY'
from colav_simulator.core.radar_occlusion import load_occlusion_grid
grid = load_occlusion_grid("tmp/m6-spike-data/straits_clamped.tif", downsample=4)
print(grid.line_of_sight_blocked(350000, 140000, 356000, 135000, 12.0, 2.0))  # True (island shadow)
PY

# PPI panel screenshot
python3 -m http.server 8031 --bind 127.0.0.1 &          # repo root
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --screenshot=output/sango-radar-s1/ppi-panel.png --window-size=560,640 \
  --virtual-time-budget=6000 --hide-scrollbars \
  "http://127.0.0.1:8031/tests/web_gui/radar-ppi-visual.html"

# web suite (node 22)
node --test tests/web_gui/*.test.mjs
```

## Parameter traceability (contract <-> code)

| parameter | source | code |
|---|---|---|
| sensor_id=1 / `radar_x` / `mast_top_xband` | sensor-model-v1 §2/§3 | `SensorId.RADAR_X`, `RadarXParams.mount_id` |
| scan period 2.5 s (24 rpm) | contract §4 `async_jitter` | `RadarXParams.rpm=24` -> `scan_period_s` |
| sigma_r 8 m / sigma_theta 1 deg | contract §4 `noise` | `sigma_range_m`, `sigma_azimuth_rad` |
| clutter 5e-7/m2 | contract §4 `clutter` | `clutter_rate_per_m2` |
| spokes 2048 / ranges [0.75..24] nm | milliampere-ch5 §5.1 (task spec) | `spokes_per_revolution`, `range_scales_nm` |
| antenna 12 m / VBW 25 deg / blind ring 54-68 m | milliampere-ch5 §4.3 | `antenna_height_m`, `vbw_deg`, `blind_ring_m` |
| mast blind sector (configurable table) | milliampere-ch5 §4.2 / IMO SN.1/Circ.271 | `blind_sectors_deg` |
| radar horizon 4.12(sqrt h1+sqrt h2) m | milliampere-ch5 §4.3 (W2) | `horizon_range_m` |
| PD(SNR) Swerling-0, Pfa 1e-4 | domain doc 02 §2.3 (Angelliaume E7 anchor, Albersheim check) | `detection_probability_swerling0` |
| He 2024 parameterized clutter | domain doc 02 §2.3 (H7) | `_generate_clutter` (Poisson points + compound amplitude) |

## Known S1 boundaries

- Clutter regeneration in the PPI panel is a browser-side deterministic
  realization of the same parameterized process (seed + rate + decay + sea
  state via the additive `radar_ppi` envelope field), not a bit-identical
  replay of the backend draw; blip positions come from the real backend
  measurement cache.
- The real-strait DEM lives under `tmp/` (local scratch, not git-tracked);
  sensors degrade to no occlusion when the path is absent
  (`load_occlusion_grid` returns None, `ppi_descriptor.occlusion=false`).
