# Deployment 3D / OpenBridge AR implementation acceptance

Date: 2026-09-20. Baseline: `e9bb3ec2`. Development branch: `codex/deployment-3d-ar`.
User approved specification #78, then added the FCB45 GLB and target-model download manifest.

## Implemented

- Deployment H / N / C / 3D; reversible chart framing, bridge/chase/top camera, rings, task/prediction/history lines and evidence-based future time labels.
- One Playback → Projection → display boundary; final frames bypass Canvas secondary interpolation. Camera time never integrates physics. Mode switches create no runtime-control requests.
- Official OpenBridge 1.0.1 POI Layer / Vessel / Card; grouping, edge hints, shared selection, unavailable facts, and generation guards. Group trigger accessibility label is a documented vendor patch.
- Local Cesium 1.133.0 + Proj4 2.19.10; ETRS89 UTM metadata, georeferenced ENC mesh, run-bound image requests, explicit illustrative ellipsoid-zero height.
- User FCB45 GLB plus 12 complete CC0 target models; source URLs, hashes, measured bounds, axis/waterline registry, local textures and visual-only target overrides. Partial Ro-Ro stern is excluded from the runtime catalog. Missing models use labeled position markers.

## Verification

| Gate | Evidence / result |
|---|---|
| Frontend regression | `node --test tests/web_gui/*.test.mjs`: **362 passed**; `node-tests.log` |
| Metadata / transport | Focused pytest: **13 passed**; `python-focused.log` |
| Existing backend failures | Two failures reproduced on untouched main baseline: deprecated algorithm selector expects retired behavior; standalone VO test omits required execution speed envelope. `python-baseline-failures.log`. No full-backend-green claim. |
| Coordinate CRS | 50 reference points across zones32/33 compared with EPSG6172/6173→4326 backend reference; ≤0.5m gate passes. Cardinal directions and wraparound covered in Node tests. |
| ENC mesh | 3,072 interior triangle samples per zone, maximum interpolation error ~0.001373m against exact geodetic conversion; `mesh-georegistration.json`. This is numerical registration error, not ENC survey accuracy. |
| GLB transform | 13 active assets: local textures, SHA256, four cardinal headings, runtime45m×8m and waterline anchor checks; `model-transforms.json`. |
| Real view switching | 20 actual Deployment 2D/3D round trips: same run ID and CREATED state; zero session mutations and no additional browser telemetry connection. `deployment-switches.json`. One subsequent auxiliary Python read-only probe is listed separately. |
| Resource lifecycle | 20 renderer reentries: exactly one root/canvas per entry, zero roots after exit; `lifecycle.json`. Five real Session Replacements clear old roots; `session-replacements.json`. |
| Real telemetry | Isolated VO run advanced under5× and paused at263.5s; 3D and shared presented frame retained the pause. This does not certify solver/COLREG behavior. |
| UI | H/N/3D pressed semantics, C action, Enter/Space switching, three camera presets, target-card selection, official overlap-group expansion, offscreen hints, night theme and2× framebuffer smoke checked. `display-checks.json`; double density was injected through the same render-scale path, not a physical Retina-device test. |
| Failure handling | EngineHTTP503 restores2D; WebGL context loss restores2D with no root; all GLBsHTTP503 retain selectable POIs/position markers. `engine-failure.json`, `context-loss.json`, `model-failure.json`. |
| Offline resources | Local-only CSP (`connect-src 'self'`, local scripts/assets, permitted local WASM); final benchmark has zero external resource requests. No external map service/token dependency. |
| Performance | **FCB +16 mixed-class targets**,1920×1080,DPR1,300s,AppleM3/ANGLE Metal: **p95 frame interval16.8ms**, median16.7ms,17/17models ready, no render errors. `benchmark-glb-final.json`. Warm mode entry62.1ms. |
| Static checks | Ruff check on changed Python passes; `git diff --check` passes. Existing whole-file Ruff-format differences in unrelated parts of `gui_server/main.py` were left untouched. |

Initial generated-hull benchmark missed the33.3ms gate at33.4ms; bounded statistics and avoiding repeated POI DOM mutations reduced it to17.7ms. The supplied-GLB rerun then passed at16.8ms. Old benchmark files remain as history; the final GLB run is the delivered asset configuration. Cesium diagnostic bounding spheres are conservative engine culling values, not physical hull radii.

## Standards review

No confirmed blocker. One non-blocking coupling: the scene reads chart-owned selection/layer/ENC state. This deliberately reuses the existing authority for this feature; a renderer-framework refactor was not introduced.

## Spec review

Fixed all reported actionable items: full-frustum checks and proper edge directions, cancellable initialization before Viewer construction, camera-follow retained on clicks, truth-only chart control disabled in3D, fallback Entity picking, late model rejection generation guards, and asset-load timeout retry. Clarified shared selection: an explicit3D selection remains selected on return to2D; an old saved ID does not overwrite the user's new selection. Asset follow-up review found no confirmed transform, security or disposal defect.

Review result: Standards0blocking findings (1coupling observation); Spec reported interaction/lifecycle gaps, now corrected. This report concerns Web visualization only; it makes no L4 acceptance, maritime certification, full6DOF, sensor-registration or real-vessel digital-twin fidelity claim.

## Reproduce

```sh
node --test tests/web_gui/*.test.mjs
.venv/bin/python -m pytest tests/test_scene_3d_contract.py tests/test_web_transport.py -q
npm ci --prefix tools/web_3d --ignore-scripts
node tools/web_3d/coordinate-acceptance.mjs
node tools/web_3d/model-acceptance.mjs
```

Run an isolated application on8013, then `python3 tools/web_3d/serve_qa.py` and open `http://127.0.0.1:8015/tests/web_gui/scene-browser.html`. The fixture is deterministic renderer evidence, not a simulated solver acceptance run. `?dpr=2`, `?failure=engine`, and `?failure=model` exercise the respective display cases. Do not point the fixture's control tests at the user's active8010 session.

## 8010 deployment

Integrated into main as `5b69ea27` and `599ef071`. Restarted the existing `com.marine.colav-simulator.frontend` LaunchAgent; its historical ENC preparation took about100s. Restored the original CREATED overtaking/Mid-MPC/Original-GNC configuration. Before/after Run Specification objects are exactly equal; the restart generated a new run ID, with no simulation progress discarded. Actual8010 exposes H/N/C/3D and loads FCB45 and target GLBs. See `deployment.json` and `8010-chase.png`. Refresh cached browser documents after updating; the fresh document uses one current OpenBridge bundle.

No unrelated tracked source files were modified. Three earlier task drafts were backed up under the path in `deployment.json` before selective integration. No push or pull request was created.
