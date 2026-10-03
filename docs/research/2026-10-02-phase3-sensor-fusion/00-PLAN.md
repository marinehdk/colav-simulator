# 阶段3 计划：传感器与融合数字孪生（2026-10-02）

状态：**已裁决开工（2026-10-02）**。裁决：默认 tracker S6 末翻转｜LiDAR 接触点 v1 旁路｜IR=温度 tag 简化模型｜桅杆基准=FBX 实测 12.98m｜#88 关票。追加需求（用户原话要点）：**主孪生视口可切传感器视角**——默认驾驶舱视角=可见光，选红外=黑白模式，选 LiDAR=探测点云视角，以此类推（经 twin-bridge-v1 加 `sensor_mode` 消息演进）。milliAmpere 论文真本=`paper/milliAmpere- An Autonomous Ferry Prototype.pdf`（5.5MB 真本，含大量图，作视觉/能力基线；research-materials/tmp/milliampere1.pdf 系反爬废页禁引）。前置：阶段2 已收官（#89 关，P3 残留 `017ab142` 清零）；a4000 延后接入。

子调研（本目录，全部一手来源/行号锚点）：
- [milliampere-ch5-fcb45-layout.md](milliampere-ch5-fcb45-layout.md) — 域需求+FCB45 布局+仿真参数表+输入契约草案
- [repo-sensor-seams.md](repo-sensor-seams.md) — 本仓库接缝与缺口（行号锚点）
- [unity-sensor-sim-survey.md](unity-sensor-sim-survey.md) — Unity/HDRP 实现路线（官方确认/社区/推断分级）

---

## 0. 目标（用户原话要点 → 可验证形态）

> 支持船载 X 波段雷达、激光雷达（点云视角）、白光+红外摄像头（桅杆分布）、AIS 显示；围绕 45m FCB 设计传感器分布；持续分辨、跟踪、融合；为避碰对象形成真实目标信息，为运动预测模型提供高置信度数据前提。

**完成 = 以下六条可验证**：
1. 目标信息链从「GodTracker 直拷真值」切换为「传感器量测 → 融合跟踪 → 确认航迹」：雷达+相机检测+AIS 三源进融合，输出带**存在概率/置信度**的航迹列表（数据产品可导出）。
2. X 波段雷达模型：spokes/rpm/量程档/海杂波（He 2024 参数化）/陆地遮挡（GEBCO DEM）/桅杆盲区扇形/异步漏检；web PPI 面板 spoke 直绘。
3. Unity 桅杆传感器机位族按 FCB45 实测布局（空气高 12.98 m）：EO×5+IR×4+PTZ 双光谱；IR 温度 tag 灰度渲染；LiDAR 深度→点云（VFX Graph）+噪声；各路可 web PiP 副流（640×480@1–2 Mbps）。
4. AIS 目标层：IMO SN.1/Circ.243 符号（睡眠/激活/危险/丢失）+信息卡+与融合航迹关联显示。
5. IPDA 存在概率三层断路贯通（接口→快照字段→决策消费），置信度不再占位 0.0。
6. YOLO 检测框经 observations 端点进后端 tracker（后端唯一受控新增面）。
7. **传感器视角切换（主孪生视口）**：驾驶舱视角默认可见光（EO）→ 选红外=黑白热像 → 选 LiDAR=点云视角 → 雷达 PPI/AIS 为 web 面板态；切换经 twin-bridge-v1 `sensor_mode` 消息（只加字段），视口工具条常驻传感器模式按钮组。视觉基线参照 milliAmpere 论文（`paper/milliAmpere- An Autonomous Ferry Prototype.pdf`）第 5 章图组。

## 1. 架构（分层数据流）

```
┌─ Unity sango（视景层，非权威）───────────────────────────┐
│ 桅杆传感器机位族（CameraViews 扩展）                        │
│  EO×5 / IR×4 / PTZ ——FramePublisher 多实例(5556/+)         │
│  LiDAR: HDRP depth→compute→VFX 点云(视景+PiP, 不进 IPDA)   │
│  IR: 材质温度tag+灰度ramp CustomPass                        │
└──────┬─ ZMQ(检测帧) ───────────────────────────────────────┘
       ▼
┌─ a4000/Mac YOLO 服务（既有）─► DetectionResult(ZMQ 5557) ──┐
│                                                              │
│   ┌─ colav-simulator 后端（权威层，受控新增）──────────────┐ │
│   │ POST /api/sessions/{id}/observations  ◄─ georef 检测框 │ │
│   │ sensing.py ISensor 族：                                  │ │
│   │  RadarX(升级: 杂波/遮挡/盲区/漏检)  LidarContact(旁路)   │ │
│   │  ExternalCameraSensor(observations)  AIS(既有旁路)      │ │
│   │ tracker: vimmjipda(+存在概率贯通) ── GodTracker 退役诊断│ │
│   │ tracks{pos,vel,cov,existence_prob,quality,sources[]}    │ │
│   └──────┬─ WS 1.0 全量(tracks 不再只有 compact 剥除路径) ──┘ │
│          ▼                                                   │
│  web_gui：AIS 层(IMO 243 符号) + 航迹/协方差/存在概率着色      │
│           + PPI 面板 + 传感器 PiP + 目标卡置信度               │
└──────────────────────────────────────────────────────────────┘
```

三条铁律（沿阶段2 四原则演化）：
1. **权威在后端**：量测/杂波/遮挡/融合/置信度全部 Python（可单测可复现）；Unity 只做视景与原始帧发布，不做目标裁决。
2. **传感器=场景内组件+采集层噪声+帧对齐契约**（CARLA/AWSIM 共性架构，调研C §6）：每传感器独立挂点+时钟戳，进同一 SFD 契约。
3. **加性演进**：observations 端点+tracks 新字段+SFD 扩展全部"只加"；既有 compact-v1/twin-bridge-v1 消费者零破坏。

## 2. 里程碑（15-25 人日）

| 段 | 内容 | 验收 | 估 |
|---|---|---|---|
| **P3-S0 契约冻结** | sensor-model-v1（SFD 扩展，milliampere 档 §6 草案→冻结 `sango/Docs/contracts/` + C# DTO + 回环）；observations-v1 端点 schema；tracks 置信度字段 schema；GodTracker 退役审计（Config god_tracker 默认翻转影响面） | 三契约文档+双侧回环测试；审计报告 | 1-2d |
| **P3-S1 X 波段雷达** | RadarX 模型（spokes 2048/rpm 24/量程档/He2024 杂波/GEBCO 陆地遮挡/桅杆盲区 54-68m 环/VBW 25°/异步漏检）+ web PPI 面板（canvas spoke 直绘+余辉） | 杂波统计单测（CFAR 域符合）、遮挡几何单测（DEM 剖面）、PPI 截图、探测率-距离曲线存证 | 3-4d |
| **P3-S2 相机链贯通** | Unity 桅杆机位族（FBX 锚点：桅顶 12.98m/舯前 2.1m）EO×5+IR×4+PTZ；IR 温度 tag+灰度 ramp；FramePublisher 多实例；**sensor_mode 视角切换（EO 默认/IR 黑白/LiDAR 占位）**进 twin-bridge 演进与视口按钮组；georef（像素→NE，相机内外参+姿态链）；后端 ExternalCameraSensor+observations 端点；YOLO 帧回传进 tracker | IR/EO 各一路上屏+进融合端到端；**EO↔IR 切换流内可见（黑白模式生效）**；georef 误差 ≤ 船长级（~45m @2nm）存证；EditMode+后端单测 | 3-5d |
| **P3-S3 LiDAR 点云视角** | HDRP depth→compute→VFX Graph 点云+CARLA 式噪声（dropoff/大气）；**sensor_mode=lidar 主视口切换为点云视角**；web PiP 副流；近距接触点旁路显示（不进 IPDA） | **主视口 LiDAR 模式切换流内可见（点云可辨船/岸/浮标）**+PiP+噪声参数表存证 | 2-3d |
| **P3-S4 AIS 显示层** | IMO 243 符号 SVG（睡眠三角/激活矢量/危险红闪/丢失×）+AIS 目标卡（MMSI/SOG/COG/龄期）+与融合航迹关联（AIS:5 旁路色） | 符号对照表截图+龄期告警+关联显示；web 测试 | 1-2d |
| **P3-S5 融合贯通+置信度** | IPDA 三层断路修复（sensing 接口→TrackSnapshot 字段→encounter_lifecycle 消费）；tracks 带 existence_prob/quality/sources；web 渲染（目标卡置信度/协方差椭圆/存在概率着色）；高置信航迹数据产品（导出端点+fixture） | 断路三层各一单测；web 图层截图；数据产品 schema+样例；同场景 god vs 融合航迹对拍（容差定义清楚） | 4-6d |
| **P3-S6 收口** | E2E：FCB45+2 目标船全传感器会话（雷达+相机+LiDAR 视景+AIS+融合+置信度上屏，Evaluation twin 全链复用）；默认 tracker 切换（Config 加项）；双轴 review | E2E 探针+录屏；review APPROVE；阶段收口报告 | 2-3d |

## 3. 硬边界（防蔓延）

1. 真实传感器硬件接入不在本阶段（延后批，两阶段构想档在 `docs/research/2026-09-29-dt-sensor-replay-paper-survey.md`）。
2. 不训练新检测模型（YOLO 沿用 yolov8n 级）。
3. **LiDAR 不进 IPDA**（点目标假设不匹配；点云=视景+旁路接触点）。
4. **不做运动预测模型本体**——本阶段只交付"高置信度确认航迹"数据产品，预测模型是下一独立立项。
5. 后端改动白名单=observations 端点+sensing 模型+IPDA 贯通+tracks 加性字段；既有 REST/WS 契约不破坏（compact-v1 剥除策略不动，tracks 走全量 transport 或专用字段演进）。
6. 采购零支出；a4000 批延后（LiDAR/IR 渲染 Mac 先行，a4000 只影响并发与分辨率档）。
7. RACON/雷达视频编码等检索空白项不做（调研C 确认无开源先例，自研无收益）。

## 4. 风险

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 杂波/遮挡模型与既有 IPDA 调参失配（跟踪掉链） | S1 先出探测率-杂波统计基线；S5 对拍以 god 航迹为对照非真值平权；参数全场景化 |
| R2 | georef 精度不足（相机→NE 误差大） | S2 用已知标定物（浮标/岸线）实测锚定；误差>阈值则降级为"框显示不进融合"开关 |
| R3 | 默认切融合 tracker 引爆既有 GNC/评估基线（大量既有测试假设 god） | 切换=Config 项且默认值翻转放 S6 末，跑全量回归后才翻；god 留诊断 |
| R4 | Unity 多相机发布带宽（Mac 单机） | 副流限 1-2 路@640×480 1-2Mbps；按需开 |
| R5 | 范围蔓延成"半个科研" | 硬边界 §3；每段验收命令级 |

## 5. 裁决记录（2026-10-02，用户确认）

1. **默认 tracker 切换时点**：S6 末全量回归后翻转 ✅
2. **LiDAR 接触点**：v1 仅旁路显示 ✅
3. **IR 模型档位**：温度 tag+灰度 ramp 简化模型 ✅
4. **桅杆高度基准**：FBX 实测 12.98m（待船东总布置图再校）✅
5. spec issue 发布：裁决后即发 ✅；**#88 关票**（感知线已被 M9+阶段3 覆盖，工作台已交付 7c7b1f3e）✅
6. **追加**：传感器视角切换（EO/IR/LiDAR 主视口）为 S2/S3 验收项 ✅

## 6. 与既有工作的衔接

- #88（Aeolus 参考+在船目标感知）：其感知线已被 M9+阶段3 覆盖，Aeolus 布景线若仍有效请在裁决时说明（建议关票或拆残项）。
- 延后批清单：a4000 Linux 宿主（阶段2 遗留）+ 真实传感器接入（本阶段边界外）——未来合并为"硬件接入批"。
- M10 backlog（浮态缩放等视觉项）不阻塞本阶段。

## 7. 完成记录（2026-10-02 收口，P3-S6）

各段 commit 与验收数字一览（行号/断言细节见各段 output 目录 README 与 commit message）：

| 段 | commit | 验收 |
|---|---|---|
| P3-S0 契约冻结 | `83d1cb61` | sensor-model-v1 / observations-v1 / twin-bridge sensor_mode 演进三契约 + C# DTO 回环；GodTracker 退役审计（本目录 audit） |
| P3-S1 X 波段雷达 | `27328286` | RadarXBand + He2024 杂波/DEM 遮挡/盲区单测 + PPI 面板（`output/sango-radar-s1/`，PD-距离曲线/杂波统计/真实 DEM 遮挡存证） |
| P3-S2 相机链 | `5aa50fa2` | 桅杆机位族 + IR 灰度 + observations 端点 + YOLO 前向进后端；EO↔IR 流内切换（`output/sango-twin-s2/`） |
| P3-S3 LiDAR | `a78e9819` | 点云视角 + LidarContact 旁路 + web LiDAR un-pending（`output/sango-twin-s3-lidar/`） |
| P3-S4 AIS | `17b96aa1` | IMO 243 符号层 + 目标卡 + 融合航迹关联（`output/sango-ais-s4/`） |
| P3-S5 融合+置信度 | `238a8c6f` | IPDA 三层断路 + §6 快照字段 + confirmed-tracks 数据产品 + god vs 融合对拍（`output/sango-fusion-s5/`） |
| P3-S6 收口 | （本段 commit） | 默认 tracker 翻转 + 全传感器 E2E + 双轴 review（见下） |

### S6 验收数字（2026-10-02）

- **翻转**：D3 `to_dict` 只在 True 写键（dump 回环不再复活 God）+ 三态回环单测；D1
  `Config.god_tracker=False`；D2 UI 默认/prewarm/policy `default_tracker_id="vimmjipda"`，
  `tracker_ids=("god","vimmjipda")`，god 保留并列（00-PLAN R3"god 留诊断"）。
- **后端全量 pytest**：翻转前后三全量 stash 对照（口径 `--ignore=tests/test_colreg_scoring.py`，
  段错误文件域外隔离，见台账）：裸 HEAD 基线 45F/2441P/10S → S6 工作树终轮 46F/2444P/10S，
  其中 45 例 = 与裸 HEAD 逐条相同的预存集合，2 例翻转引入（D1 场景默认链语义 + D2 元组
  镜像钉值）均已按任务约束修绿并文件级复验——**有效终态失败集合 = 预存基线，零新增**。
  （注意：任务时点台账 9 红；S6 当日环境退化批 +36 例与段错误文件均为裸 HEAD 复现，与
  S6 diff 无关——详见 preexisting-failures.md，供后续立项。）
- **web**：`node --test tests/web_gui/*.test.mjs` 465/465。
- **EditMode**：Unity 零改动，免跑（基线 506/506 不变）。
- **四既有探针**（8010 launchd kickstart 后）：obs（默认 vimmjipda 会话）PASS、lidar PASS、
  ais PASS、tracks PASS。
- **新 E2E 探针**：`node tools/sango_phase3_e2e_probe.mjs` PASS（`output/sango-phase3-e2e/`）。
- **翻转实证**：无 tracker_id 请求 → 会话 `spec.tracker_id=vimmjipda`；显式 `tracker_id="god"`
  会话可建（回退路径 1）；场景显式 `god_tracker: ''` 回环保真（D3 单测）。
- **场景装配写档**：`scenarios/head_on.yaml` 自有船 sensors 头部插入 `radar_x: {}`
  （= RadarXParams 契约锚点默认值；首位的理由：web PPI 绑定首个量测组）。
- **阶段发现（遗留立项）**：外部 vimmjipda 接口仅消费 legacy Radar 通道（上游 isinstance
  过滤，外部仓库本阶段不触碰）→ radar_x 进 vimmjipda 融合需外部仓库工作；vimmjipda 会话
  目标进入 2km 雷达量程前无航迹（设计使然）。
- **终审修复批披露（2026-10-02，P1-1b，与 radar_x 缺口同级）**：YOLO/相机量测已通到 KF
  链（`external_cameras:` 显式装配，P1-1a 修复）；默认 vimmjipda（外部仓）只消费 legacy
  Radar——radar_x 与相机两源进外部融合属外部仓库立项（与 radar_x 缺口同级披露）。
