# Spec: Sango 本机仿真设置与船载动态目标识别

评审基线：`cbad8202`。研究依据：[RESEARCH.md](RESEARCH.md)，Aeolus-Ocean v1.11 公开 README/Release/论文及用户四张参考图。此规格扩展阶段一展示能力；保留既有后端与物理资格边界。

## Problem Statement

目前 Simulation 面板没有完整实现参考图 1：环境数与 agent 数是占位，船型仅改变预览，DEV、航点生成、感知参数没有形成可执行设置。既有 YOLO 视频主要是外部机位识别本船，没有证明船载前向相机在自身航行时识别其他运动目标船。控制面板长期遮挡船上视野，天气与导航展示也缺少参考图中的手动接管、独立降水和感知状态。

## Solution

增加可操作的仿真设置页及紧凑航行 HUD，保留真实海峡，并增加可复现的程序化实验场。复用 Unity/HDRP、已有船模编目、Perlin、航点运动学、视觉浮态、雷达真值显示及本机 YOLO/ZeroMQ。每个可编辑控件必须有真实效果；不能支持的物理谱型、训练或融合能力明确说明，不用假控件冒充实现。

增加确定性前向遭遇：本船从桥楼/艏机位航行，其他船沿固定或种子化航线持续运动；相机可在设定距离内观测目标，真实 YOLO 回传可见框与置信度。昼、暮、夜、雾、雨及较高海况各提供独立证据。

## User Stories

1. As an operator, I want a Simulation Setup page, so that I can configure a run without inspecting Unity components.
2. As an operator, I want actual environment and vessel counts, so that I can verify settings are applied rather than placeholders.
3. As an operator, I want a real-strait mode, so that I can retain the existing geographically sourced scene.
4. As an operator, I want a procedural experiment mode, so that I can run local repeatable demonstrations without overwriting real terrain.
5. As an operator, I want up to 16 local environments with at most 32 vessels in total, so that I can demonstrate multiple local encounters.
6. As an operator, I want explicit rejection of invalid counts, so that applying settings cannot partially replace a scene.
7. As an operator, I want environment spacing and optional travel enclosures, so that local experimental groups can be separated.
8. As an operator, I want independent ocean-current drift control, so that I can see its effect on vessel motion.
9. As an operator, I want honest HDRP sea-spectrum approximation controls, so that I can vary sea appearance without assuming a certified PM/JONSWAP/TMA implementation.
10. As an operator, I want optional islands in each procedural environment, so that I can create repeatable terrain demonstrations.
11. As an operator, I want Perlin scale, height, octaves, falloff, smoothness, persistence, lacunarity and offsets, so that terrain settings have visible reproducible effects.
12. As an operator, I want a fixed seed, so that the same setup can be replayed.
13. As an operator, I want island controls disabled in the real-strait mode, so that synthetic settings cannot alter geographic terrain.
14. As an operator, I want waypoint arrival distance and marker visibility controls, so that navigation displays match the configured route.
15. As an operator, I want valid waypoint minimum/maximum spawning distances, so that generated routes respect the chosen environment.
16. As an operator, I want random, crossing and head-on waypoint demonstrations, so that I can reproduce different target geometries.
17. As an operator, I want actual vessel selection from the existing catalog, so that the selection changes the simulated vessel as well as its preview.
18. As an operator, I want to choose a designated ego vessel, so that cameras, radar, vectors and controls follow the same vessel.
19. As an operator, I want onboard and external camera views, so that I can inspect both navigation and encounter geometry.
20. As an operator, I want start, pause, resume and reset controls, so that demonstrations do not require hotkeys.
21. As an operator, I want settings application blocked while a run is active, so that an unconfirmed draft cannot silently replace the running scene.
22. As an operator, I want explicit local waypoint navigation, so that the UI does not claim a trained collision-avoidance policy.
23. As an operator, I want manual arrow-key takeover and return to waypoint navigation, so that I can demonstrate user control without competing motion writers.
24. As an operator, I want speed and waypoint vectors plus waypoint markers, so that navigation intent is visible.
25. As an operator, I want computer vision enabled separately from ground-truth demonstrations, so that YOLO results cannot be confused with simulator truth.
26. As an operator, I want the detection interval to affect actual frame publication, so that throughput and latency can be adjusted.
27. As an operator, I want confidence to affect actual inference/filtering, so that the setting is more than a label.
28. As an operator, I want a target observation distance, so that the onboard camera can observe nearby moving targets with a documented truth-assisted selection boundary.
29. As an operator, I want radar range and sweep in metres and RPM, so that the controls match the reference's units.
30. As an operator, I want truth radar and image detection identified separately, so that the display does not imply sensor fusion.
31. As an operator, I want moving vessels registered to radar and overlay truth lists, so that relevant targets are not omitted from the display.
32. As an operator, I want an onboard forward-encounter demonstration, so that I can verify another moving vessel is detected while the ego vessel moves.
33. As an operator, I want visible YOLO live, empty-detection and stale/unavailable states, so that a missed detection cannot be reported as a successful result.
34. As an operator, I want unobscured coloured outline boxes and readable confidence labels, so that targets remain visible beneath the overlay.
35. As an operator, I want detector input without GUI/annotation feedback, so that previous results do not contaminate subsequent inference.
36. As an operator, I want compact weather controls for time, clouds, fog, Beaufort, wind and wave direction, so that I can change conditions while watching the horizon.
37. As an operator, I want independent rain, snow and visual thunderstorm effects, so that these conditions are not confined to a single preset.
38. As an operator, I want optional wet-lens visual effects, so that camera weather affects the rendered sensor image with an explicit approximation boundary.
39. As an operator, I want daytime, dusk, night, fog, rain and rough-sea encounter recordings, so that scene visibility and live detection can be assessed separately.
40. As an engineer, I want existing position/attitude ownership preserved, so that new controls do not add a second integrator.
41. As an engineer, I want setting changes and restarts to release owned objects and materials, so that repeated local runs remain usable.
42. As an engineer, I want actual 2560×1440 wall-clock performance evidence, so that offline recordings cannot masquerade as real-time performance.
43. As an engineer, I want settings, model identity, detection results and capture timestamps retained, so that the videos are reproducible.
44. As an engineer, I want local CPU inference and a local Mac player, so that completion does not depend on A4000 or a Windows binary.
45. As a reviewer, I want separate Standards and Spec review results against the committed baseline, so that coding quality cannot hide missing features.
46. As a scenario author, I want to add, edit and remove individual target vessels, so that I can build a usable next-stage collision-avoidance test scene.
47. As a scenario author, I want each target's vessel type, initial position/heading, speed and stationary/straight/waypoint motion, so that target behaviour is not limited to one global vessel or route preset.
48. As a scenario author, I want to save and reload a scene definition with stable vessel IDs and explicit east/north/yaw units, so that the next-stage backend adapter can consume repeatable scene inputs.

## Implementation Decisions

- Add one local visual-simulation controller that owns applied configuration, environment/vessel creation, designated ego selection and run lifecycle. It is separate from the backend Active Session and never claims backend Session Authority.
- Keep a mutable setup draft separate from applied values. Validate the entire draft before scene mutation; fail with actionable errors. Start/pause/reset/selection use public controller operations. Applying a draft while running requires an explicit pause first.
- Real-strait mode is one geographic environment. Procedural mode may create up to 16 groups; total vessel count is capped at 32. These are local motion demonstrations, not independent ML-Agents episodes or parallel policy training.
- Reuse vessel catalog prefabs and waterline/yaw metadata. Preserve the existing true-terrain scene when entering/leaving experimental mode. Procedural island controls never change original DEM/GEBCO heights.
- Per-vessel overrides contain a stable local ID, catalog type, initial east/north offset, heading in degrees, speed, motion mode and optional waypoint list. Scene editing applies only while paused/stopped. Save/load a versioned local scene definition, validate it entirely before replacing the current visual run, and document the existing east=x/north=z and positive-yaw/radian backend mapping. This is a scene handoff definition, not backend session creation or collision-avoidance execution.
- Individual add/remove operations target the single-environment scene-authoring mode; a grid uses its generated actor counts. Removing a target preserves other local IDs, and adding can reuse a vacant slot. Current ego removal requires selecting another ego first.
- Extend existing Perlin and waypoint facilities only where requested controls need real effects. Preserve legacy defaults and existing scenes. Enclosures must affect allowed travel, and invalid waypoint distances must be rejected rather than silently changed.
- Existing waypoint motion remains the sole horizontal/yaw writer. Visual buoyancy remains the vertical/roll/pitch writer. Current drift and manual control are inputs to that motion path, not separate transform integrators.
- Bind ego camera, vectors, radar and controls to one selected vessel. Build appropriate mounted viewpoints using catalog dimensions and reuse calibrated FCB45 mounts. Provide a repeatable forward encounter with separately moving targets.
- Use native HDRP Water; sea-spectrum settings are explicitly visual approximations. Do not write a replacement ocean shader or claim exact PM/JONSWAP/TMA physics.
- Confidence semantics follow the current YOLO threshold: higher values reject more low-confidence boxes. Do not copy ambiguous reference wording. Detection interval affects publication; model threshold must receive the configured value. Required frame/result envelope fields remain compatible; any added frame metadata fields are optional and documented.
- Capture the scene camera before screen-space control/detection overlays to remove annotation feedback. Preserve full-screen pixel dimensions, original timestamps, upright image orientation and existing freshness/sequence validation. Video presentation may add the native detection layer, but detector input must stay free of HUD/previous boxes.
- Draw transparent outline boxes and readable labels; distinguish real YOLO, authoritative empty result, stale result and explicit truth mode. Never label GT as live inference.
- Observation-distance camera selection may use simulator truth to choose a nearby target; label this clearly. It is not an estimated target range, world-position tracker or sensor-fusion result.
- Radar stays truth-based visualisation. Convert RPM to angular speed consistently. Display truth radar separately from image detections; do not create an apparent fused track.
- Reuse runtime Unity UI idioms with a setup page and compact in-run controls. Ensure references and owned render resources are released on reset/exit; avoid duplicate cameras, event systems or motion owners.
- Add visual precipitation/wet-lens/thunderstorm controls using engine-native effects. Mark them as visual approximations; avoid downloaded/AI-generated assets and unsupported physical sensor claims.

## Testing Decisions

- Confirmed seam (user accepted 2026-10-01): public simulation-control operations (apply validated setup, read applied values/ego/counts, start/pause/reset/manual control), plus the native Mac player as the end-to-end boundary. Reuse the existing control/transport boundaries rather than private implementation details.
- Test external behaviour, not private fields, scene-object implementation names or formulas recomputed from the implementation. Existing public waypoint, camera, weather, island and transport seams provide prior art; prefer one controller-level integration seam over many new micro-seams.
- Use vertical red→green slices: invalid setup leaves the prior run intact; selected vessel and ego binding change actual behaviour; motion pause/reset/current/manual controls remain coherent; local environments respect the total budget; inference controls reach real processing.
- Run focused tests during implementation and the full EditMode suite once the final implementation is stable. Unity compilation is the typechecking gate. Run Python protocol checks where inference metadata changes.
- Native player acceptance requires actual 2560×1440, wall-clock rendering ≥30 FPS for the default supported demonstration, no failed/non-finite water queries, actual ego and target movement, and genuine fresh detections of another vessel from an onboard viewpoint. Report 32-actor scaling performance separately; never extrapolate default FPS to the maximum workload.
- Capture separate day/dusk/night/fog/rain/rough-sea windows. Record rendering, fresh-result availability and nonempty detections separately. Do not require a model to invent detections in adverse weather; record misses honestly.
- Keep model identity, settings, publisher interval, confidence, source timestamps and real result JSON with each recording. Native frames and expected target geometry may support IoU checks, but do not publish AP/precision/recall claims without a defined annotated evaluation cohort.
- Final review uses user-confirmed `cbad8202` as the fixed point and this specification as the Spec source; Standards and Spec agents run separately. Commit final reviewed implementation on the current branch.

## Out of Scope

- Reproducing Aeolus binary internals, private assets or private policy weights.
- ML-Agents/PPO/imitation training, trained COLREG avoidance, episode/reward design or a new learning pipeline.
- Exact spectral ocean replacement, certified 6-DOF hydrodynamics, measured RAO, sea-trial or camera calibration.
- Genuine radar/sonar echoes, target-world-position estimation, temporal tracking/data association, AIS/radar fusion or certified detection accuracy.
- Backend WebSocket/REST control-loop integration, new COLAV decision logic, AGX/A4000/Windows deployment. Existing backend architecture and algorithms remain intact.

## Further Notes

Research confirms Aeolus currently publishes a Windows binary rather than a Unity source project. Reuse its publicly described behaviours as reference, and existing open technologies as implementation building blocks. The public baseline also has limitations: only its motorboat policy is sufficiently trained, one vessel type per environment, simplified foam and documented setup hangs. These are not reasons to recreate defects.

The user confirmed both the public-control/native-player test boundary and `cbad8202` review baseline, and selected AGENTS.md with the existing GitHub issue workflow. All implementation and acceptance remain local.
