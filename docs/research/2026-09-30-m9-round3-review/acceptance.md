# M9 验收档 — 尾迹/夜景/后端握手 + FCB45 hero 接入（20260930）

## 概述

M9 两线并行：①M8-C 三票 FAIL 转出的观感 backlog（尾迹系统、夜景光照）实施与实机修复迭代；②后端真握手（仿真帧→YOLO→DetectionResult→overlay 回传）端到端打通。执行中途用户交付 Blender 自建 **45m FCB45 真船模**，裁决：判定轮次前完成接入替换占位 hero（FcbHoubei），三票判定打在真 hero 上。

## 修复台账（实施工作流四闸后，实机迭代发现→修复）

| # | 问题 | 根因 | 修复 |
|---|---|---|---|
| 1 | DetectionResultConsumer 不在场景 | Editor bootstrapper 烘焙场景未重跑，player 打包旧场景；B1/A1 文件所有权缝 | M1/M2E/M6 三处 overlay GO 补挂 typeof(DetectionResultConsumer)；场景门→player 门重跑 |
| 2 | 号灯全灭（渲染层） | ①Unity Quad 正面被 Cull Back 剔除（billboard +Z 朝相机=正面朝相机）；②ApplyObservationBearing 把 alpha 一并乘 nits（320）→白爆 | 专项修复员钉死双根因；因后续近景眩光新交互（FCB45 桅杆贴近桥楼相机），**最终裁决回退号灯视觉到 M8-C 已证基线**（交叉双面 quad+12 nits，round2 评审判定位置/颜色正确），测试同步回退 |
| 3 | 号灯 320nits 白爆风险 | 灯不可见期间盲调补偿值 | 回退至 12（M8-C 同级可读度） |
| 4 | 水线环超船巨环（2.5×船宽横椭圆） | ①hull 包围盒扫进 NavigationLightsRig 30m 拖尾 quad（AABB 膨胀）；②BuildRing 椭圆轴 X/Z 装反（长轴横贯 beam） | 包围盒按祖先名剔除 rig 子树（excludedForeign=8）；椭圆轴换位（X=beam、Z=LOA），追拍视角实证贴壳 |
| 5 | 握手模式 fps 60→18 | 逐帧 ReadPixels+EncodeToJPG 吃满帧预算 | FramePublisher 加 1/30s 最小间隔节流（线协议/seq 单调不变，契约 §5 已修订）；同机跑检测服务仍 ~15-20fps（YOLO MPS 同机竞争），无 publisher 基础模式 58-75fps |
| 6 | HullWaterlineDecals 播放器 ArgumentNullException | HDRP/Decal 被构建 strip（Shader.Find=null） | BuildProjectors 入口 null 守卫，干净降级（湿感贴花缺失入 backlog） |
| 7 | 渲染场景无 WakeFoamRig（尾迹零） | M8RecordingRunner 只加载落盘场景，场景烘焙早于新组件 | M6 Build 门重跑后 rsync；后续轮次均含 |

## 门禁终态

- **EditMode 399/399**（FCB45 接入后含 catalog/placement/场景 smoke ×9 新测试；号灯回退同步回退其钉子测试）
- **sango.app 构建 Success**（rebuild8，含全部修复+FCB45 hero）
- **fps 干净协议（High，无旗标，78s 窗）**：暖机 41.5 后 6 窗 58.2–74.9（≥30 闸门 2× 余量；本机 vsync 未锁定口径，与 M8-A 60.0×6 差异为启动上下文，如实记录）
- **a4000 出片**：九段 **10809/10809 @Constant60**（bow/bridge/chase/overlook/topdown-day + bridge-atmo 60s + 三夜段）
- **EditMode 历次**：实施工作流 460 口径（工作流树）→ lamp 修复 391 → FCB45 后 400 → 回退后 399（口径漂移系测试增删，全绿状态一致）

## 后端真握手（端到端实证）

- 链路：sango.app `--sango-publisher`（ZMQ PUB 5556，topic sango.frame，JPEG 60）→ `.venv-detector` YOLO 服务（ultralytics yolov8n，~25-35ms/帧）→ PUB 5557（topic sango.detection，DetectionResult JSON）→ Unity DetectionResultConsumer（后台线程+ConcurrentQueue+新鲜度门）→ **B 键 overlay 渲染 YOLO live 框（实拍 `boat 0.83`/`boat 0.61` 标签+置信度）**，GT 兜底并存
- 契约：`sango/Docs/contracts/detection-return-v1.md`（新增）；`frame-publisher-v1.md` §5 节流修订
- Python 侧自检：replay→service→订阅端 rx=tx=6/6；实机 detector rx/tx 累计 3 万+ 帧
- DEMO 限制：握手模式同机 fps ~15-20（检测服务同机竞争）；trial version 水印=授权形态（Unity Personal trial），非代码问题

## FCB45 hero 接入（用户交付 Blender 模型）

- 素材：FCB45_Unity.fbx（LOD0 68,618 tris）+ 12 色 flat HDRP/Lit 调色板（无贴图）；catalog v3 条目（LOA 45m/beam 8.63m 含护舷/吃水 1.55m/bowYaw 0° 双源互证）
- hero 四处接线全换（VesselFcb45），锚地船群保持；水深门 PASS（航路最浅 −46.9m）；wake rig 自派生（loa=45/beam=8.6 实证）；EditMode 400/400（当时口径）
- 保留：桨舵 Pivot×5（后续动画可接）、M1 场景仍 houbei 占位

## 已知余项（转 M10 backlog）

1. 尾迹 ribbon 断续贴片感（纹理 UV 密度/发射连续性）——topdown 六连帧可见动态尾迹但块状
2. FCB45 桅灯近景眩光（bridge-night 相机贴桅杆，点光 600lm 洗桅杆；真实桥楼夜摄亦有眩光，观感取舍归评审）
3. 地平线白带、双艏绿楔（houbei 时代挂账，FCB45 后部分消除待复判）
4. 湿感/boot-top 贴花播放器降级缺失（HDRP/Decal strip；如需恢复走 Graphics always-included shaders）
5. 握手模式帧率（同机 YOLO 竞争；远机部署可解）
6. VesselBuoyancy 全局参数未按 LOA 取参；WaypointFollower 航速沿用 42m 占位值
7. trial version 水印（授权形态）

## 材料

- 九段 master mp4 + 720p 代理（<30MB 全可直读）+ 定时刻 contact sheet（15s 段 6 帧/2.5s，atmo 12 帧/5s）：本目录 `m9r3-*.mp4`、`proxy/`、`sheets/`
- **判定（第三轮）：FAIL（运动 2/尺度 3/光照 2，三票高度收敛）**——聚合表与共识命中见 `score-aggregate-r3.md`，findings 转 M10 backlog（浮态响应幅度/Kelvin 尾迹几何/号灯可见度/切雨 ramp/地平线白带）；DEMO 可展示不受影响
