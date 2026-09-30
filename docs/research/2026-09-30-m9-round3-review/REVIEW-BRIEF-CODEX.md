# MASS 数字孪生仿真平台 — 完成情况总结（CODEX 评审简报，20260930）

对照两次调研的定义：调研1（PHASE1-PLAN，三阶段/阶段1=M0-M3）+ 调研2（更新计划，插入逼真性阶段 M4-M8）。本简报按计划口径逐项对账，供评审与修复派单。

**当前主线状态**：`main @152d8b4f`（本地未 push，remote=marine）；EditMode **399/399**；sango.app 可演示；a4000 出片链全通；三票制观感判定三轮 FAIL 如实入档（findings 转 M10 backlog）。

---

## 一、四段总览对账

| 阶段 | 计划定义 | 状态 | 证据锚 |
|---|---|---|---|
| **阶段1 展示 Prototype（M0-M3）** | 四画面 demo + 四颗缝钉子 | **✓ 完成** | PHASE1-PLAN.md 逐项打勾；#79-#86 全关；probe 30/30；双 demo build |
| **逼真性阶段（W1+M4-M8）** | 海峡场景/船队/地形/布景/双档出片 | **✓ 完成**（M8-C 后延伸 M9 修复批） | docs/research/2026-09-29-m5..m8*/acceptance.md；M8-C 三票 ×2 轮 |
| **M9（本轮延伸，计划外）** | 无计划条目——两线：观感 backlog 修复 + 后端握手 + 用户交付 FCB45 hero 接入 | **✓ 完成（观感判定 FAIL 如实入档）** | docs/research/2026-09-30-m9-round3-review/ |
| **阶段2 后端闭环** | WebSocket compact-v1 遥测环 + 3 REST + YOLO 真推理回传 | **◐ 一半提前完成**：检测回传环（FramePublisher↔YOLO↔overlay，即"首验=YOLO live 框上屏"）已端到端实证；**WebSocket 遥测消费环未开工**（契约冻结未动） | contracts/frame-publisher-v1.md、detection-return-v1.md；tools/sango_detector_*.py |
| **阶段3 完整数字孪生** | 真实传感器/融合/避碰/agx 部署 | **未动**（方向预留）——符合计划硬边界 | — |

## 二、阶段1（M0-M3）逐项对账

| 里程碑 | 计划验收 | 状态 | 备注 |
|---|---|---|---|
| M0 环境就绪+海面冒烟 | git 纳管；1440p ≥30fps 存证；fps<30 触发 R1 回退 | **✓** | Mac 主线达标，**R1 回退链未触发**；后续所有 fps 记录均为带 Script Interactions 的 6 船逐三角形查询口径 |
| M1 海况天气 GUI | beaufort-water-mapping.md；B0→9 波高可感；昼夜/雾距截图 | **✓** | Perlin 岛场景后按 M6 裁决保留为**开发代理场景**（M1-Weather.unity） |
| M2 浮力+四画面 | 四画面条款表+录屏×4+双击可演示+fps 复测 | **✓** | 俯视 COLREG 轨迹/仿真面板/夜间船艏/桥楼自航；灯反射首日专项不达标→假反射 streak 兜底（沿用至今=round2 评审"位置/颜色正确"的基线） |
| M3 检测叠加+四钉子 | probe 30/30 收帧；EditMode 存证；detection-result 契约冻结 | **✓** | 四钉子①②③④全落；probe 存证在 evidence/m3-build-log.md |

## 三、逼真性阶段（W1+M4-M8）逐项对账

| 里程碑 | 计划验收 | 状态 | 备注/偏离 |
|---|---|---|---|
| W1 启动批 | — | **✓** | — |
| M4 船-水工艺 | 水线/艏波/尾迹 | **✓ 实施；观感后判定不足** | 初版=HDRP WaterDecal 双 decal+速度门（decalGate 契约，M8 pre-roll 依赖）；M9 升级为粒子+ribbon（见 §五） |
| M5 免费船队 | 8 件 CC-BY 入库署名，$0 | **✓** | Kenney Watercraft 8 档；**偏离：hero 外包推迟项被用户自制 FCB45 取代（见 §五）** |
| M6 真实地形 | GEBCO+GLO-30 DEM、S2 tile、29 tile 场景、管线一键重跑、fps≥30 | **✓** | Terrain Lit 免费路线；区域中心浮点原点；M1 场景保留；数据红线合规（无 Esri/Google/ENC 提取） |
| M7 布景大气 | 四辨识要素+三档大气+默认视程≥8km | **✓** | 16 STS 岸桥+1916 箱堆、东西锚地 6+6 槽、IALA 浮标、渡轮/拖轮、渔排；三档大气（含 M1 挂账雨 VFX 归此）；**偏离：树卡 Fab Megaplants 人闸未消费→基本体卡兜底（F3 挂账，来源链在 M7 acceptance §F3）**；F1 处置=新增第五机位"瞭望" |
| M8 双档+出片 | Mac 低配∥a4000 全质；60s×N 出片；三票制打分 | **✓** | Quality 双档 L 键（High=全量/Low=tile 流送）；Recorder 5.1.7 管线+九段脚本；**三票制 round1/round2 均 FAIL（运动 2/尺度 3/光照 2）**，round1 根因（船静止/夜段泄漏）修复后 round2 仍 FAIL→转 backlog |

## 四、M9（本轮，20260930）——计划外延伸的两线 + FCB45

### A 线：观感 backlog 修复（实施工作流三路+实机迭代）

**实施**：①尾迹系统粒子化（WakeFoam 三件套：艏浪粒子×2+位置历史 ribbon+水线泡沫环；High=粒子+ribbon 主视觉/Low=decal 现状；速度门复用 WaterDecalSpeedGate，decalGate 契约与 M8 pre-roll 不变）②夜景光照（夜间曝光地板 −3EV 暮光渐入、天气切档 2.5s 渐变、号灯 billboard 圆形化实验）③后端握手回传链（见 C 线）。

**实机迭代修复台账**（验收档 §修复台账 #1-#7，全部有实证）：
1. DetectionResultConsumer 未挂场景（烘焙场景未重跑）→ 三 bootstrapper 补挂+场景门重跑
2. 水线环超船巨环 → 双根因：hull AABB 扫进兄弟 rig 30m 拖尾 quad（按祖先名剔除）+ **环椭圆轴 X/Z 装反**（换位）
3. 号灯全灭 → Quad 正面朝相机被 Cull Back 剔除 + alpha 被 nits 连乘白爆（专项修复员双根因钉死）
4. 号灯处理裁决：修复后近景眩光新交互（FCB45 桅杆贴桥楼相机）→ **整体回退 M8-C 已证基线**（交叉双面 quad+12nits），测试同步回退
5. FramePublisher 加 1/30s 节流（线协议/seq 单调不变，契约 §5 修订）
6. HullWaterlineDecals 播放器 HDRP/Decal strip 崩溃 → null 守卫降级
7. 渲染场景烘焙陷阱（bootstrapper 改动须重跑 M6 Build 门再出 player/rsync）

### B 线：FCB45 hero 接入（用户交付 Blender 模型，取代 hero 外包人闸项）

catalog **v3** 第 9 档（LOA 45m/beam 8.63m/吃水 1.55m）；bowYaw 双源互证（构建期 MeasureBowYaw + 交付方 import 验证 JSON）；12 色 HDRP/Lit 平涂调色板（无贴图）；hero 四处接线全换、锚地船群不动；M6 水深门 PASS（航路最浅 −46.9m）；桨舵 Pivot×5 保留（后续动画可接）；M1 场景仍 houbei 占位。**注意事项（给 CODEX）**：重导 unitypackage 必须走 M5FleetPipeline 重建（bump 版本戳），不能直接导包覆盖。

### C 线：后端真握手（=阶段2 的"首验"项，提前完成）

链路：`sango.app --sango-publisher`（ZMQ PUB 5556，multipart [topic][FrameMetadata JSON][JPEG]）→ YOLO 服务（`.venv-detector`，ultralytics yolov8n，25-35ms/帧）→ PUB 5557（topic sango.detection，DetectionResult JSON）→ Unity `DetectionResultConsumer`（后台线程+ConcurrentQueue+DetectionFreshness 新鲜度门）→ **DetectionOverlay live 框上屏（实拍 boat 0.83/0.61 标签+置信度）**，GT 兜底并存，B 键切换。契约 `detection-return-v1.md` 冻结；工具 `tools/sango_detector_service.py`（含 --selftest）+ `sango_detector_replay.py`。Python 侧回环 6/6。

**阶段2 剩余（未开工，契约冻结照计划执行即可）**：WebSocket `/ws/sessions/{id}?transport=compact-v1` 遥测消费（truth[]/plans/playback）+ 3 条 REST + 首日 psi=90° 艏向回归 + 后端+Unity 同机宿主裁决。

## 五、客观门禁终态（全部可复跑）

| 门 | 终态 | 复跑命令/位置 |
|---|---|---|
| EditMode | **399/399** | `Unity -batchmode -projectPath <abs>/sango -runTests -testPlatform EditMode -testResults <xml>`；计数口径历史 124（阶段1）→241→337（M8）→399（M9 增删后），全绿状态一致 |
| 播放器构建 | Success | `-executeMethod Sango.Editor.M6StraitSceneBootstrapper.BuildStraitPlayer`；**场景改动须先跑 `M6StraitSceneBootstrapper.Build`（烘焙门）再出 player** |
| fps | 58-75（暖机 41.5），≥30 闸门 2× 余量 | 播放器跑 78s grep Player.log `overlays fps (10 s avg)`；注：vsync 未锁定口径（与 M8-A 60.0×6 差异=启动上下文，非性能回退） |
| a4000 出片 | 九段 **10809/10809 @Constant60** | 配方：rsync（排 Library/Temp/obj/Logs/Builds/UserSettings/tmp）→ `ssh a4000 nohup run-shots.sh`；**铁律 -force-vulkan 显式 + GDM :0**；帧 901/段+3601(atmo) |
| 帧发布探针 | probe 30/30（M3 起） | `tools/sango_zmq_probe.py --count 30` |
| 握手 E2E | YOLO live 框上屏 | detector 服务+`--sango-publisher` 启动+B 键 |

## 六、三票制观感判定（诚实结论）

- **round1 FAIL**（出片侧根因：镜头脚本未驱动自航+段间状态泄漏）→ 修复重出
- **round2 FAIL**（运动 2/尺度 3/光照 2）→ findings 转 backlog
- **round3 FAIL（同分，三票收敛）**——协议改进（同源定采样：contact sheet+720p 代理 <30MB）消除抽样分歧后，三票一致命中：
  1. **零浮态**（运动主因）：九段零纵摇/横摇/升沉；客观锚=VesselBuoyancy 日志 target(h/r/p)≈0——**姿态响应未随 Beaufort 缩放，修复路径明确、收益最大**
  2. **尾迹无 Kelvin V**（尺度主因）：ribbon 随航迹延伸但"串珠虚线/恒一倍船宽/无扩散臂"；艏浪原地斑块
  3. **号灯单点方形眩光**（光照主因）：masthead 方核+巨晕、舷灯不可见、水面零光池、段间一致性差
  4. 切雨断崖（SetRate 无 ramp）、雨丝粗竖条伪影、地平线白带（round1 起挂账）
- 正面：atmo 昼→暮渐变（三票认可）、太阳耀斑碎光（"全九段最佳"）、尺度参照正确
- **按协议出口：findings 转 M10 backlog 交人闸**；DEMO 可展示不受影响

## 七、M10 backlog（评审+修复的主战场，按建议优先级）

1. **浮态响应幅度随海况缩放**——VesselBuoyancy target≈0 根因；一处修改直抬运动轴
2. 尾迹 Kelvin V 几何（V 臂+横波+展宽）——大项，粒子工艺之上的波浪动力学
3. 号灯可见度（舷灯亮度/水面光池/段间一致性；billboard 实验死代码 `NightGrade/LampSpotTexture.cs` 可裁决删留）
4. 雨 SetRate ramp+雨丝伪影
5. 地平线白带（M6 远景水色分块）
6. WakeFoamRig 插桩日志精简（build 日志含 hullBounds 调试信息，可留可删）
7. 湿感/boot-top 贴花 player 降级缺失（HDRP/Decal strip；如需恢复走 always-included shaders）
8. VesselBuoyancy 未按 LOA 取参；WaypointFollower 航速沿用 42m 占位值（FCB45 已 45m）
9. 握手模式同机 fps 15-20（YOLO MPS 竞争；远机部署可解）；trial version 水印（授权形态）

## 八、硬边界合规自检（累计版）

| 边界 | 状态 |
|---|---|
| 不 DRL/不写 COLREG 裁决/不锁步/不做帧级同步 | ✅ 未越 |
| 不联调 Colav 后端（阶段1-逼真性期间） | ✅ 阶段2 遥测环未动；握手仅走 M3 冻结的缝（未改后端） |
| 不接传感器硬件/真实 YOLO 不入阶段1 | ✅ YOLO 属阶段2 首验项，提前且未入主 demo 默认路径（默认 OFF，旗标启用） |
| 采购零支出（路线 A） | ✅ FCB45=用户自制（非采购非外包），Kenney/免费件署名入库 |
| AI 生成资产不入最终线 | ✅ |
| 数据红线（Esri/Google 3D Tiles/MPA ENC 永不提取） | ✅ 全走 GEBCO/GLO-30/S2 免费合法栈，GDAL 脚本主干版本化 |
| 海面 shader 停投/Crest 不买/Perlin 岛保留为代理 | ✅ |

## 九、给 CODEX 的重点评审面（按文件）

高优先（本轮新写/大改，实机暴露过 bug 的区域）：
- `Runtime/WakeFoam/WakeFoamRig.cs`（包围盒过滤+环轴修复+档位门；含插桩日志）`WakeFoamCore.cs`（纯曲线）`WakeFoamTexture.cs`
- `Runtime/FramePublisher.cs`（节流协程——注意与"关闸零成本"验收故事 5 的兼容论证）
- `Runtime/DetectionResultConsumer.cs`+`Vessels/DetectionFreshness.cs`+`DetectionOverlay.cs`（线程/队列/新鲜度门；EditMode 禁 socket 的缝设计）
- `Runtime/WeatherController.cs`（夜地板 .Override 口径+切档渐变对 M8 确定性路径的无劫持论证）
- `Editor/M5FleetPipeline.cs`+`Vessels/VesselCatalog.cs`（v3 第 9 档；重导防护）
- `tools/sango_detector_service.py`（协议对齐 DetectionResult.cs 字段）
- 契约：`sango/Docs/contracts/detection-return-v1.md`（新）+`frame-publisher-v1.md` §5（修订）

中优先：`Editor/M1/M2E/M6 bootstrappers`（consumer 挂载+hero 接线）、`HullWaterlineDecals.cs`（守卫）、`BoatWaterDecals.cs`（双驱注释）、`SimulationPanel.cs`、测试文件（WakeFoam*/NightGrade*/Detection*/M5Fleet*/M4BAdapterTests 回退）。

修复派单建议：M10 backlog 项 1（浮态）可立即派单；项 2（Kelvin V）建议先出设计小稿再实施；项 3-5 打包为一个 polish 批。

## 十、环境事实（复跑必读）

- 本地 Unity：`/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app`（batch 单实例）；a4000：`~/unity-install/6000.3.24f1`，license 已激活（RDP+Hub Google OAuth），**-force-vulkan 必须显式 + X 必须用 GDM :0**（Xvfb/xrdp 黑帧）
- 检测器 venv：仓库根 `.venv-detector`（pyzmq+ultralytics），权重 `models/yolov8n.pt`（均已 gitignore）
- 工作树：存量脏文件（TerrainM7 材质/网格、Settings volume profiles、M1/M2E 场景、tmp 删除）**有意不提交**，评审时勿误判为本轮改动；M9 改动=提交 9bd7cfbd/60de5369/152d8b4f 的 diff 范围
