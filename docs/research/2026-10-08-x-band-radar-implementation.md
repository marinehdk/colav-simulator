# X 波段船载雷达：SENSOR → RADAR 合并与实现调研

调研日期：2026-10-08

范围：回答“移除底栏 PPI 后，SENSOR → RADAR 如何呈现”，审计当前 `COLAV-Simulator` 传感器链，给出尽可能接近真实船载 X-band 雷达的分阶段实现方案。本文件只做调研和设计边界，不实现雷达模型，不修改 planner 安全基线，不启停服务。

## 结论先行

当前工作树已完成这项 UI 合并：`ppiPanel` 已放入 `ownshipSensorPage`，SENSOR 卡直接显示 X-band PPI；`ppiBtn`、`ppiCloseBtn` 和 live truth mini-map 入口已移除；底部视角组保留 `DT`。证据为 [`web_gui/index.html:336-380`](../../web_gui/index.html)、[`web_gui/index.html:591-598`](../../web_gui/index.html) 和 [`tests/web_gui/radar-ppi.test.mjs:231-249`](../../tests/web_gui/radar-ppi.test.mjs)。

本轮 UI 验证：Node v22.22.3 运行 `node --test tests/web_gui/*.test.mjs`，487/487 通过；浏览器在现有 CREATED 会话中确认 SENSOR 内嵌 PPI、底栏无 PPI、DT 标签、0.75↔6 NM 切换无需新遥测。打开封存 run `86898501` 后，SENSOR 明确显示“此回放未记录 X 波段雷达量测”。本轮未运行会替换用户会话的 twin 探针，未重跑后端或 Unity 套件。以上验证只覆盖 UI 替换，不证明下面的雷达模型升级已完成。

产品上只保留一个雷达入口：进入 SENSOR 页面后打开 `RADAR`，雷达画面默认是后端 `radar_x` 传感器产生的 PPI/雷达视频；底栏只保留视角切换入口，不再保留独立 `PPI` 按钮。下面旧 `RADAR`/mini-map 的描述是本轮 UI 合并前的代码审计，用来说明语义缺口；当前 live SENSOR 已由 PPI 接替，但 PPI 的后端量测和前端杂波语义尚未改变。

这不是把现有小型 `RADAR` 图换成另一个前端画布那么简单。当前系统存在三种语义不同的“雷达”:

| 合并前名称/来源 | 合并前语义 | 当前 live UI 状态 |
|---|---|---|---|
| `web_gui/modules/radar-mini-map.js:12-40` | 直接使用 `snapshot.obstacles` 的目标/真值位置，叠加风险颜色和前向扇区；只能称为态势缩略图 | live SENSOR 已移除该入口；模块/测试仍是旧语义审计证据 |
| `web_gui/modules/radar-ppi.js:160-223` | 目标点来自后端 `measurements`；杂波由浏览器重新生成；扫线为前端动画 | 已成为 live SENSOR → RADAR；目标点部分来自后端传感器，杂波和强度仍不是后端同一扫描证据 |
| Unity `RadarOverlay` | `Transform` 真值位置 blip；类注释明确写着无真实信号处理/地杂波 | Unity 视景原型，不能作为后端雷达输入；[`sango/Assets/Scripts/Runtime/RadarOverlay.cs:8-15,112-135`](../../sango/Assets/Scripts/Runtime/RadarOverlay.cs) |

因此，替换目标应定义为：`SENSOR → RADAR = 后端唯一 X-band 扫描证据的显示层`。雷达原始回波、雷达检测点、融合航迹、AIS 和 ENC 可以在同一面板分层显示，但每层必须标注来源和时间语义；没有雷达检测证据时，不能用 truth/obstacle 位置补成“雷达回波”。

最重要的实现约束是：杂波不能继续由前端另造。后端应生成一次扫描包，检测器、融合器、PPI 和回放都消费同一 `scan_seq`；前端只绘制后端给出的回波/检测结果。

## 外部规范和真实设备锚点

### IMO 约束的是功能和显示语义，不是某一种渲染算法

IMO MSC.192(79) 的范围要求雷达相对于本船显示其他船、障碍、危险物、航标和岸线，并要求雷达视频、目标跟踪、EPFS 位置数据和地理参考数据能够集成显示；AIS 用来补充雷达，而不是替代雷达。[IMO MSC.192(79), §1](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.192%2879%29.pdf)

该标准适用于船载雷达安装，不因频段或显示类型改变；文档明确覆盖 X-band 和 S-band。对本项目的直接含义：

- `RADAR` 主层必须有雷达视频/回波语义，不能只有目标图标。
- AIS、融合航迹和海图应是可区分的叠加层，不能把 AIS 符号伪装成雷达回波。
- 量程环应随当前量程显示，量程读数必须明确；IMO §5.10.1 的标准量程档位包含 0.25 nm、0.5 nm 等短程档位，当前 UI 从 0.75 nm 起是产品档位选择，不应被写成 IMO 全部量程实现。IMO §5.11 对固定量程环给出当前最大量程的 1% 或 30 m（取较大值）的系统准确度要求。[IMO MSC.192(79), §§5.10.1、5.11](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.192%2879%29.pdf)
- 处理或组合雷达信号时，应能说明信号来源和处理来源；这要求 UI 显示 `RADAR VIDEO / DETECTIONS / TRACKS / AIS` 的来源标签，而不是只显示一组绿色点。[IMO MSC.192(79), §5.35](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.192%2879%29.pdf)
- 目标跟踪、CPA/TCPA、航迹和 AIS 关联属于雷达系统的上层功能，不能与原始回波层混成一个“安全分数”。§5.25 涉及 tracked-target capacity/accuracy，§5.28 涉及 AIS target information，§5.30 要求雷达/AIS target association；它们不是 raw-video 精度条款。[IMO MSC.192(79), §§5.25、5.28、5.30](https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.192%2879%29.pdf)

另一个容易混淆的边界：IMO §5.2 的一般 range/bearing accuracy 是 1% 当前量程或 30 m（取较大值）以及约 1° bearing accuracy；§5.5 的 40 m range discrimination / 2.5° bearing discrimination 是特定短程测试条件下的 discrimination 条款，不是所有量程的显示精度。厂商某型号的 25 m range discrimination、1%/10 m range accuracy、±1° bearing accuracy 也不是同一层级。本文把它们分别标成“IMO 规范锚点”和“Furuno profile 锚点”，不把厂商数值倒写成 IMO 通用指标。

这里的引用是产品语义和验收参考，不表示本 Web UI 是经过 IMO 型式认可的船载雷达。

### 真实 X-band 设备给出参数范围，不应被误写成单一硬件型号

Furuno FAR-15x3 官方规格 PDF 给出的商用 X-band profile 是：9410 MHz ±30 MHz，12/25 kW，开式波导天线水平波束约 1.9°/1.35°，垂直波束 20°，24/48 rpm，最小量程和距离分辨率 25 m，量程精度为当前量程的 1% 或 10 m（取较大值），方位精度 ±1°；不同量程使用不同脉宽和 PRR。[Furuno FAR-15x3 官方规格 PDF](https://www.furuno.com/files/Brochure/324/upload/FAR-15x3_BB_EN.pdf) 这些数值是该型号 profile 的直接规格摘录，不是 IMO 通用指标；PDF 下载端当前偶发 fetch failure，后续提交时应保留该官方 URL 和原始 PDF 快照校验。

Furuno 的雷达基础资料也明确指出，天线水平波束宽度决定方位分辨率，X-band 开式天线可以达到约 0.75° 的水平波束；垂直波束通常约 20°/25°，用来降低横摇和纵摇影响。[Furuno Radar Basics](https://www.furuno.com/en/technology/rader/basic/index.html)

当前 `RadarXParams` 的 24 rpm、2.5 s 扫描周期、6 nm 默认量程和 2048 spokes 可以作为工程化仿真档位，但不能直接宣称等于某台真实设备；尤其当前 `antenna_height_m=12m` 不是 NTNU milliAmpere 船体已证实的雷达相位中心高度。后面的 NTNU 证据显示，最有依据的初始 profile 是 Simrad HALO24，而不是先假设 Furuno 12/25 kW 开式雷达。Furuno 参数保留为独立商用 profile 对照，不应混进 milliAmpere 设备结论。

### 一手仿真资料的可借鉴边界

官方 Gemini 仓库将 Unity 项目定位为可同时提供光学、LiDAR 和 Radar 模拟数据并提供 API 的海事传感器平台。[Gemini 官方仓库 README](https://github.com/Gemini-team/Gemini)

Gemini 的原始论文（Vasstein et al., 2020）描述了从同一 Unity G-buffer/渲染状态并行产生多种传感器数据的架构；论文也明确其雷达简化了 RCS、海杂波和 Doppler，不能把“Unity 有雷达画面”当作高保真证据。[原始论文 DOI/出版社链接](https://doi.org/10.1088/1757-899X/929/1/012032)；本仓库全文材料见 `docs/research/2026-09-30-mass-situational-awareness/06-simulation-digital-twin.md:15-20`。

关于海杂波，Stokes 波面驱动的动态海杂波仿真论文给出物理海面、雷达 footprint 和遮挡效应的建模方向，但它是岸基雷达研究，不能直接替代低掠射角船载 X-band 标定。[The Dynamic Sea Clutter Simulation of Shore-Based Radar Based on Stokes Waves](https://www.mdpi.com/2072-4292/14/16/3915)

## 当前仓库传感器链：代码事实

### Python 是传感器和量测权威，Unity 是视景与原始帧发布端

冻结契约明确写出：Unity/C# 不消费 SFD，不做目标裁决；量测、杂波、遮挡、融合和置信度全部由 Python 负责。[`sango/Docs/contracts/sensor-model-v1.md:1-19`](../../sango/Docs/contracts/sensor-model-v1.md)

Unity 当前的 `frame-publisher-v1` 是相机原始帧发布协议：localhost ZeroMQ PUB `tcp://127.0.0.1:5556`，三段 multipart 为 topic、元数据 JSON、JPEG。[`sango/Docs/contracts/frame-publisher-v1.md:1-31`](../../sango/Docs/contracts/frame-publisher-v1.md)；其默认关闭、最高 10 Hz、异步 GPU 读回和 JPEG 编码也在同一契约中声明。[`sango/Docs/contracts/frame-publisher-v1.md:33-71`](../../sango/Docs/contracts/frame-publisher-v1.md)

Twin bridge 也把边界写死：Unity 直接向后端取 live compact-v1 或 replay window，浏览器不做遥测中继；Radar PPI/AIS 是 Web 面板态，不经 `sensor_mode` 这条 Unity 视口桥。[`sango/Docs/contracts/twin-bridge-v1.md:1-10,28-43`](../../sango/Docs/contracts/twin-bridge-v1.md)

所以 X-band 雷达实现应留在 Python 传感器/量测/融合链；Unity 可以以后承担雷达视景或设备外观，但不能另生成一套雷达杂波再送回后端。

### `ISensor`、配置和场景装配

`ISensor.generate_measurements()` 的旧接口是 `list[(do_idx, z)]`，其中输入是 `(do_idx, state, length, width)` 真值障碍物列表。[`colav_simulator/core/sensing.py:26-69`](../../colav_simulator/core/sensing.py)

`Config` 解析 `radar_x`，`SensorSuiteBuilder` 实例化 `RadarXBand`；未配置传感器时仍回退为旧 `Radar()`。[`colav_simulator/core/sensing.py:149-220`](../../colav_simulator/core/sensing.py)

当前 ownship 场景已经显式装配 `radar_x`，并将它放在旧 `radar` 之前，使 PPI 绑定第一组雷达量测：[`scenarios/head_on.yaml:33-46`](../../scenarios/head_on.yaml)。这是当前产品演示的正确装配方式，但仍只是一个场景证据，不代表所有场景已切换到 X-band。

### `RadarXBand` 已有的物理/统计退化

当前模型已经超出旧的圆形“真值雷达”，参数包括：2048 spokes、24 rpm、0.75–24 nm 量程、天线高度、垂直波束盲环、桅杆盲区、8 m 距离噪声、1° 方位噪声、Pfa、SNR/RCS、目标高度、漏检、Beaufort 海况、泊松杂波、纹理形状、每扫描输出上限和 DEM/landmask 遮挡。[`colav_simulator/core/sensing.py:475-546`](../../colav_simulator/core/sensing.py)

检测链实现了：

- 24 rpm 对应的异步 beam-crossing 更新；只在天线扫过目标方位后产生一次测量。
- 由船长/船宽估算 RCS，再按距离衰减计算 SNR，以 Swerling-0/erfc 近似计算 Pd。
- 垂直波束近距盲环、水平相对船首盲区、雷达地平线和 DEM 视线遮挡。
- Beaufort 因子和径向衰减的泊松海杂波点，附带 per-scan cap。

对应源码入口和实现范围：[`colav_simulator/core/sensing.py:549-635`](../../colav_simulator/core/sensing.py)、[`colav_simulator/core/sensing.py:709-865`](../../colav_simulator/core/sensing.py)、[`colav_simulator/core/sensing.py:867-913`](../../colav_simulator/core/sensing.py)。已有验证覆盖盲环、盲区、地平线、Pd 曲线、异步扫描、泊松统计、海况缩放、DEM 遮挡、SFD schema 和 KF 接线：[`tests/test_radar_xband.py:1-9,49-178,191-261,264-427`](../../tests/test_radar_xband.py)。

### 当前模型与真实雷达之间的关键缺口

1. `spokes_per_revolution=2048` 目前主要进入 descriptor；后端没有真正的“方位 spoke × 距离 bin”强度矩阵。`_scan()` 是目标/杂波点列表，前端扫线也是连续动画，不是逐 spoke 的回波。
2. `RadarXParams` 没有真实硬件的水平波束宽度、旁瓣、脉宽、PRR、发射功率、极化、接收带宽或 range-cell 分辨率；当前 beam crossing 更接近“方位穿过即采样”，没有天线方向图和 dwell/积分。
3. 目标回波仍是按船长×船宽的粗略面积 RCS，缺少朝向/海况/上层建筑/多散射中心/船尾 wake 的 aspect-dependent RCS。
4. 当前 `_generate_clutter()` 输出点，而不是 range-cell 回波幅度或 I/Q；注释称复合纹理/K-family，但实现采用 NumPy Wald texture × exponential power，需要把实际分布和 calibration ID 写清楚并用船载数据标定。
5. `generate_measurements()` 与 `generate_sfd_frame()` 都会各自调用 `_scan()`；后者明确是“alternative to—not a wrapper”，因此同一时刻若同时调用两者会得到两次不同随机扫描。要做同源 PPI/SFD，必须先生成一个不可变 scan packet，再从它派生不同视图。[`colav_simulator/core/sensing.py:614-655`](../../colav_simulator/core/sensing.py)
6. 旧量测为 `do_idx` 已知标签，目标检测实际上绕过了真实 data association；而 SFD 示例把 radar `target_hint` 设为 null。[`colav_simulator/core/sensing.py:614-635`](../../colav_simulator/core/sensing.py)、[`sango/Docs/contracts/sensor-model-v1.md:49-67`](../../sango/Docs/contracts/sensor-model-v1.md)。这对现有 KF/GodTracker 兼容有用，却不能当作无标签雷达回波检测证据。
7. 传感器用 ownship 速度推导 yaw；SFD 可带 yaw，但当前模型没有完整的天线稳定、pitch/roll、船体运动补偿和 head-up/north-up/relative-motion 模式。

这些缺口不是说当前 RadarXBand 无效。它已经是“后端产生有噪声、有漏检、有盲区、有地形和统计杂波的点量测模型”；它还不是“真实船载雷达视频/回波模拟器”。两种能力必须在验收中分开命名。

### 跟踪器和 VIMMJIPDA 接线

仿真主循环从船列表提取真值障碍物，调用 `ship_obj.track_obstacles()`，然后缓存每个 sensor 最近一次非 NaN 量测，作为 `sensor_measurements` 发布到每船帧。[`colav_simulator/simulator.py:395-427`](../../colav_simulator/simulator.py)、[`colav_simulator/simulator.py:606-633`](../../colav_simulator/simulator.py)

KF 对每个装配传感器调用 `generate_measurements()`，再按 `do_idx` 自动关联并更新；RadarXBand 的 capability flag 使外部 VIMMJIPDA 接受它，适配器把外部存在概率和实际贡献传感器写入 `TrackSnapshot`。[`colav_simulator/core/tracking/trackers.py:571-692`](../../colav_simulator/core/tracking/trackers.py)、[`colav_simulator/integrations/vimmjipda_existence.py:38-105`](../../colav_simulator/integrations/vimmjipda_existence.py)

GodTracker 仍是产品中的诊断/兼容通道：它直接复制真值状态，即使同时生成传感器量测，也不能证明雷达驱动的融合航迹。VIMMJIPDA 的 capability 接线和外部仓库当前 commit `58e4903` 是运行集成证据；外部仓库工作树当前干净但 handoff 标记该 commit 尚未 push。未 push 不等于已完成雷达资格或融合器资格，VIMMJIPDA 的 RMSE/NIS/NEES/ID-switch 等独立门仍需单独验收。

## 当前 Web PPI 的准确边界

当前 UI 合并已经完成，下面审计的是“现在 SENSOR 里的 PPI 数据行为”，不是建议把 PPI 再加回底栏。`web_gui/app.js` 已统一 live/paused envelope 的 `renderRadarPpi()` 路径；`web_gui/index.html` 只保留 SENSOR 页面里的 `ppiPanel`/`ppiCanvas`。UI 位置已解决，剩余问题是 PPI 是否真正消费同一后端扫描证据。

后端只把 `RadarXBand.ppi_descriptor()` 的参数化描述放到顶层 `radar_ppi`；它不是一帧雷达视频。[`gui_server/main.py:182-202`](../../gui_server/main.py)、[`gui_server/main.py:1863-1868`](../../gui_server/main.py)

全量 telemetry 的每船 `measurements` 是 simulator 的最近有效 legacy measurement cache。[`gui_server/main.py:1498-1522`](../../gui_server/main.py)；当前 PPI 从 `measurements[0][0]` 读有 `do_idx >= 0` 的目标点，并按前端镜像 SNR 曲线计算亮度。[`web_gui/modules/radar-ppi.js:1-19,160-223`](../../web_gui/modules/radar-ppi.js)

浏览器杂波路径是另一个随机实现：它读取 `radar_ppi` 的 rate/range decay/sea state/seed，在 `clutterPoints()` 中用 JavaScript `mulberry32` 和 Knuth Poisson 重新生成点；源码注释直接称其为 backend-independent realization。[`web_gui/modules/radar-ppi.js:96-141`](../../web_gui/modules/radar-ppi.js)

所以当前 PPI 的事实判断是：

- 目标 blip 的位置来自后端生成的 legacy RadarXBand 测量缓存，属于真实后端量测链的一部分。
- 目标 blip 没有传输真实 SNR、Pd、RCS、beam width 或回波幅度；亮度是前端按距离的 proxy。
- 杂波点不是后端这一次 `_scan()` 的杂波点；它只复现统计参数，不复现同一扫描 realization，也没有进入 tracker 的同一测量集。
- `spokes` 和 `scan_period_s` 被拿来做扫线动画，但没有后端 spoke/range-cell 强度阵列。
- `compact-v1` 会从 `truth` 删除 `measurements`、`tracks`、`colav`；[`gui_server/main.py:205-231`](../../gui_server/main.py)。当前浏览器主链使用 shared-planner transport 时仍能保留 truth 载荷，但 Unity twin 的 compact 数据面不能据此获得 PPI 原始量测；这也符合 twin bridge 对“Radar PPI 是 Web 面板态”的边界。

## 建议的目标架构

### 目标数据流

```text
场景真值 + ENC/DEM + ownship pose + 海况/天气
                         │
                         ▼
             RadarXBand.scan_once()
                         │  一个不可变 scan packet / scan_seq
          ┌──────────────┼─────────────────┐
          ▼              ▼                 ▼
      raw radar      detector/CFAR      replay artifact
   video/spokes      detections          exact scan bytes
          │              │
          │              ├─────────────► Web detection layer
          │              ▼
          │      fusion tracker (KF/VIMMJIPDA)
          │              ├─────────────► planner track input
          │              └─────────────► Web fused-track layer
          └────────────────────────────► Web radar-video layer

AIS/ENC 各自权威数据 ───────────────────► Web independent overlays
```

`scan_packet` 至少应带 `run_id/session_id`、`sensor_id=1`、`mount_id`、`scan_seq`、`sim_time_s`、beam 起止方位/当前方位、rpm/scan period、range scale、range-bin 定义、ownship pose、海况/天气 profile ID、随机实现 ID、land/occlusion 状态和 source/build hash。所有派生数据引用同一 `scan_seq`，而不是靠浏览器 `floor(sim_time / scan_period)` 猜测当前扫描。

### `RadarScanPacket` 伪接口和坐标/时间语义

下面是接口草案，字段名用于固定边界，不是要求本轮立即新增的 Python 类型：

```python
@dataclass(frozen=True)
class RadarScanPacket:
    schema_version: str                 # "radar-scan@1"
    run_id: str | None
    sensor_id: int                      # 1 = radar_x
    sensor_label: str                   # "radar_x"
    mount_id: str                       # e.g. "mast_top_xband"
    status: str                         # OK | NOT_ASSEMBLED | NO_MEASUREMENT |
                                        # STALE | DROPPED | RESET
    unavailable_reason: str | None

    scan_seq: int                       # 完成/发布的一次 revolution；不是 spoke_seq
    spoke_count: int                    # e.g. 2048，工程输出格数
    scan_start_s: float
    scan_end_s: float
    spokes: tuple["RadarSpoke", ...]   # 每 spoke 自己带 spoke_seq/t_spoke_s

    frame_id: str                       # "absolute_ne" or "ownship_local_ne"
    ownship_pose: "OwnshipRadarPose"  # north/east/yaw/pitch/roll at measurement
    range_scale_m: float
    range_bin_count: int                # e.g. 1024
    range_cell_pitch_m: float           # display/bin spacing, not necessarily resolution
    profile_id: str
    realization_id: str                 # seed/config/build digest, not UI-local seed
    configured_channels: tuple[str, ...]
    contributing_sources: tuple[int, ...]  # this packet's actual sources only

@dataclass(frozen=True)
class RadarSpoke:
    spoke_seq: int
    t_spoke_s: float
    azimuth_rad: float                  # antenna look direction, north-clockwise
    intensity_u8: bytes                 # optional P1 binary chunk, no truth labels
    returns: tuple["RadarReturn", ...] # P0 sparse form

@dataclass(frozen=True)
class RadarReturn:
    range_m: float
    azimuth_rad: float
    intensity: float
    snr_db: float | None
    detection_confidence: float | None
    source: str                         # RADAR_X; generator component labels are audit-only
    target_hint: None                   # raw/detection path has no truth do_idx
```

坐标必须显式区分：模拟器生成器可以在绝对 UTM 投影的 NE 米坐标运行；Web 显示再做 `display_n = absolute_n - enc_origin_n`、`display_e = absolute_e - enc_origin_e`，目标相对 ownship 的 range/bearing 则另做 `absolute_target - absolute_ownship`。不能把 display local NE 当成绝对 NE，也不能把 origin 减两次。`sensor-model-v1` 的 SFD 量测约定是 ownship-NED 的 `[north,east]`，因此 packet 的 `frame_id` 不能省略。[`sango/Docs/contracts/sensor-model-v1.md:49-67`](../../sango/Docs/contracts/sensor-model-v1.md)

`yaw_rad` 是船体/天线朝向，`COG` 是速度向量方向；有漂移、低速、横流或转弯时二者可以不同。head-up 画面应使用 pose yaw，COG 只作为轨迹/速度层；不可在 yaw 缺失时无条件用 COG 冒充雷达天线方向。

`scan_seq` 表示一圈扫描的逻辑序号；`spoke_seq` 和 `t_spoke_s` 表示这一圈中每根 spoke 的顺序和时间。不能用 `floor(sim_time / scan_period)` 代替 per-spoke 时间戳，也不能把一圈内的插值扫线当成新的量测。重连、seek、session replacement 后应通过 `status=RESET` 或新 run_id 明确重置。

未装配 ownship `radar_x` 时，返回 `NOT_ASSEMBLED`；没有当前有效回波时返回 `NO_MEASUREMENT`；传输落后返回 `STALE`/`DROPPED`。这些状态不能以空数组、零强度或 sensor 位置猜测来伪造“无风险”。`configured_channels` 是场景声明的传感器集合；`contributing_sources`/track `sources[]` 只列本次实际产生有效贡献的通道。配置了 radar_x 不等于当前 track 已由 radar_x 更新。

这里 `NO_MEASUREMENT` 应严格限于尚未生成/交付有效扫描；一次有效扫描中没有检测目标仍是有效观测，应使用 `VALID` 和空 detections，不能把“零检出”与“扫描不可用”合并。`sensor_id=1` 是传感器种类编号，还需 `(run_id, vessel_id, sensor_instance_id/mount_id)` 区分同种雷达实例，不能用传感器数组顺序绑定数据。

`target_hint=None` 是 raw/detection 面的硬边界。仿真真值标签可以保存在受限的 `truth_audit` sidecar，用于检测误差对照和 replay 审计，但不能进入前端 `RADAR DETECTIONS`，也不能作为真实检测传给 planner。旧 `list[(do_idx,z)]` 适配器可以暂时保留给 legacy KF/VIMMJIPDA；那条兼容路径必须标注为 simulation-association，不得与无标签 radar detection 混名。

### P1 回波格的工程输出预算

第一版 polar grid 可以选择 `2048 × 1024 × uint8`：每圈约 2,097,152 bytes（约 2 MiB）；24 rpm、2.5 s/rev 时约 0.8 MiB/s，600 s 回放原始量约 480 MiB，再加元数据、检测和压缩收益/损失。这些是本项目的工程传输/存储预算，不是真实雷达的分辨率、PRF 或性能指标。

建议 binary spoke chunks（例如每 32 或 64 spokes 一个 chunk）：JSON header 只发 scan/profile/时间/坐标/哈希，payload 用二进制 `uint8`/`uint16` 强度；Web UI 或 replay 需要时按 `scan_seq` 重组。现有 planner telemetry WS 不应因为 2 MiB/rev 变成浮点 JSON；可用独立 radar binary stream 或 replay artifact。第一版 replay 可保存 `scan/frames.bin` + manifest digest，压缩格式和 chunk 索引另行冻结。

### 分阶段实施

#### P0：先把“同一个后端量测”做成可检测证据

目标：先修正数据权威，不立即做全波电磁模型。

1. 将 `_scan()` 的结果封装为不可变 `RadarScanPacket`：目标回波记录、杂波回波记录、每条记录的 range/azimuth、`t_cross`、SNR/Pd、噪声后位置、遮挡/盲区原因和 `scan_seq`。
2. `generate_measurements()`、`generate_sfd_frame()`、tracker 输入和 Web telemetry 都从同一个 packet 派生；同一 tick 不再各自调用随机扫描。
3. 先发送稀疏回波/检测 JSON（含真实 intensity/confidence 和 scan_seq），废止 `web_gui/modules/radar-ppi.js` 的 `clutterPoints()` 生成。PPI 只绘制后端数据；前端只负责投影、颜色、量程环、扫线和图层开关。
4. 继续保留旧 `list[(do_idx,z)]` 作为兼容适配，但同时发布无 `target_hint` 的 `radar detections` 视图。planner 和现有安全验收仍使用原有 track 输入，避免把高保真雷达改造混进避碰基线。
5. 给每个回波和每个轨迹显示 `source=RADAR_X`、`scan_seq`、`t_s`、age；AIS 轨迹和融合轨迹采用独立符号/颜色。

P0 必须保护现有随机 draw 顺序和 seeded replay：新的 packet 封装应复用已经生成的 records，不在 legacy `RadarXBand` 路径中插入新的随机抽样。若 P1 需要额外 video noise/PSF draw，使用独立、版本化的 RNG stream，并保持 `radar_x_video_v1` 默认关闭；不要因为生成 UI 回波改变现有 planner 输入、track 更新顺序或安全 baseline。真值标签只写 audit sidecar，不作为前端 detection 或 planner 输入。

P0 完成条件：网络抓包能证明 PPI、tracker 和 replay 引用同一个 `scan_seq`；前端没有生成杂波；一帧后端扫描可在断开 Web 后独立回放。

#### P1：真正的极坐标扫描格和检测层

将后端原始输出从稀疏点扩展为定长极坐标格：`azimuth_bin × range_bin → intensity`。建议先用 8-bit/16-bit 量化强度和压缩二进制传输，不发送 JSON 中的浮点大矩阵。

第一版物理近似至少应分开四件事：

1. **雷达方程/SNR**：可以从当前 `snr_db()` 扩展为
   `SNR_dB = C_dB + 10log10(σ_aspect / σ_ref) - 40log10(R/R_ref) + G_two_way_dB(Δaz) - L_weather_dB - L_clutter_dB`。
   这里的 `40log10` 是点目标两程距离衰减的工程近似；`C`、RCS、weather loss、clutter floor 和 profile provenance 必须独立记录。它不是对真实发射机、接收机、传播和电磁散射的完整求解。
2. **beam PSF**：初版可用归一化单程功率 Gaussian 近似 `G_power(Δaz)=exp(-4 ln(2)(Δaz/θ_3dB)^2)`，让一个目标影响相邻方位 bin。`θ_3dB` 在此定义为单程功率全宽；单站同天线收发时，两程项是 `G_two_way_dB=10log10(G_tx_power·G_rx_power)`，而非把线性 Gaussian 直接加到 dB SNR。后续再替换为 profile 的实测主瓣/旁瓣表；必须声明单程/两程约定。2048 个角向输出格不是 2048 个独立天线分辨单元。
3. **距离分辨率与 cell pitch 分开**：物理距离分辨率由脉宽/匹配滤波带宽决定，简单脉冲可写为 `ΔR≈cτ/2`；`range_cell_pitch_m` 只是输出格采样间距。比如 6 nm / 1024 bins 约 10.9 m/bin，并不代表 10.9 m 的物理分辨率。厂商的 25 m discrimination 是双点分离性能，不能直接当作 PSF 宽度；应按 profile 的波形/处理设置 range PSF，再用指定条件下的双点测试校准和验收。
4. **检测顺序**：`raw intensity → calibration/noise floor → optional motion/antenna stabilization → sea/rain/land clutter policy → CFAR guard/training cells → thresholded cells → connected-cell grouping → centroid/extent/covariance → targetless detections → association/tracker`。每一步的 profile/version/Pfa 设定必须随 packet/replay 保存；不能先把真值船直接画成 detection，再倒推 CFAR 成功。

- 方位：采用真实 profile 的水平波束宽度、旁瓣和转速；2048 方位格可以作为过采样输出，但不能把它误称为真实天线分辨率。
- 距离：按 profile 的脉宽/距离分辨率和量程联动；Furuno FAR-15x3 的 25 m range discrimination 可作为 12/25 kW 开式雷达档位锚点。
- 目标：从船体几何生成少量 aspect-dependent 多散射中心和 RCS，而不是一个按长宽面积算出的单点；先支持船/浮标/岸线三类 profile，避免立即做完整电磁求解。
- 检测：raw video 与 detections 分开。先提供后端可复现的 CFAR 试验层（CA/OS/GO/VI 至少选一种），输出阈值、估计噪声、Pfa/Pd 和 detector version；tracker 只消费 detection packet。
- 杂波：将当前点过程保留为 fast profile；新增 compound-Gaussian/K/3MD 可配置 profile，参数由 Beaufort/风速/浪高和量程驱动；后续再加入时间/空间相关、雨杂波和岸线残留。
- 地理杂波/遮挡：用 ENC/DEM/landmask 产生岸线回波和阴影，保存每个 scan 的 occlusion mask/hash；不能只在前端把陆地画成背景色。

P1 完成条件：同一 `scan_seq` 的 polar grid 经后端 detector 产生 detections；Pd/Pfa、range/bearing error、scan period、盲环、地形遮挡、海况变化和重复 seed 均有离线证据。

#### P2：船载显示行为、运动补偿和回放

- 显示模式：head-up、north-up、course-up、relative/true motion，明确 ownship pose 使用 yaw/pitch/roll 和天线稳定状态。
- 扫描行为：beam width/dwell/integration、换量程不清空或清空回波的产品规则、echo trail、past positions、航向标记、VRM/EBL 等逐项建模；优先实现能支撑检测和人工检查的少数功能。
- 运动补偿：ownship 地速、艏向/转率、横摇/纵摇、天线安装偏置进入 scan packet；前端不根据当前视角或 sensor 位置猜分组。
- 回放：在 `decision_replay` 中保存 raw/detection/track 三层和 profile/config/build hash；replay 必须复现 scan_seq、计数、强度摘要和 detector 输出，不能只靠当前浏览器重新随机绘制。
- 性能：控制遥测仍可保持 10 Hz；雷达 scan 是 0.4 Hz（24 rpm）或 1 Hz（60 rpm）的物理事件。UI 可按 scan_seq 插值扫线，但不能把插值帧冒充新测量。

P2 完成条件：live 与 replay 使用同一个 schema；变更 range/heading mode 后，两次扫描内显示语义与量程/方向一致；暂停、重连、seek 后 scan_seq 和时间戳仍可审计。

#### P3：真机/数据回放校准

用真实 X-band spoke/PCAP 或厂商数据校准 range/bearing error、Pd/Pfa、海杂波分布、岸线残留和 scan timing。对照 AIS 只做外部参考，不能反过来把 AIS 真值塞成雷达检测。没有真实低掠射角船载数据时，必须把结果标为“统计仿真 profile”，不能标为“真实雷达回放”。

## SENSOR → RADAR 的推荐显示分层

进入 SENSOR 页面后的 `RADAR` 卡/面板建议按以下层组织：

1. **RADAR VIDEO（默认）**：后端 polar grid 或后端稀疏回波；绿色强度图，盲环/量程环/北标/航向标记来自 packet。
2. **RADAR DETECTIONS**：CFAR/检测层输出；显示点、检测强度、Pd/置信、scan age。无检测时保持空，不显示障碍物真值。
3. **FUSED TRACKS**：KF/VIMMJIPDA TrackSnapshot；显示 source、existence/quality、轨迹年龄。它不是回波。
4. **AIS**：AIS 报文/历史 AIS；显示 last-seen age、COG/SOG 和关联状态。AIS 与雷达关联应有单独符号。
5. **ENC / LAND**：可选海图、岸线、地形遮挡边界；不应覆盖雷达层使用户误把海图边界当回波。
6. **诊断栏**：`sensor_id=1`、mount、profile、range、rpm、scan period、scan_seq、sim time、source age、replay/live、detector 版本。

默认产品视图可以只打开 VIDEO + DETECTIONS，TRACKS/AIS/ENC 作为开关；但所有层的数据源在后端字段中保持可追溯。此设计直接对应 IMO 要求的雷达视频、目标跟踪、地理参考和 AIS 补充显示，同时保持 COLAV 的“每类事实一个权威来源”边界。[`docs/adr/0001-one-canonical-authority-per-threat-fact.md:1-24`](../../docs/adr/0001-one-canonical-authority-per-threat-fact.md)

## 验收和安全边界

### 必须证明的雷达事实

- **同源**：PPI、检测器、KF/VIMMJIPDA 和 replay 读取同一个 `scan_seq` / packet hash。
- **无前端伪造**：前端网络输入中含后端生成的回波/杂波强度或点；UI 不再调用 `clutterPoints()`。
- **物理几何**：range ring、range/bearing 误差、水平波束、垂直盲环、转速、扫描周期、天线安装偏置有数值证据。
- **退化性**：Pd 随距离/RCS 单调变化；Pfa/CFAR 在海况 profile 变化下可解释；漏检、异步、地形遮挡和盲区可重复。
- **融合**：RadarXBand 量测确实进入目标 tracker；GodTracker 运行只能标为 truth/diagnostic，不能作为 radar fusion PASS。
- **回放**：固定 seed/profile/build 能重建 scan_seq、packet hash、检测和轨迹；前端刷新不会改变雷达事实。
- **性能**：记录每 scan 生成耗时、发送字节数、UI 绘制耗时和丢帧；不以“画面顺滑”替代传感器采样证据。

### 不纳入本轮的内容

不立即做全波电磁传播、精确 Maxwell/射频硬件仿真、完整 Doppler/IQ 链、真实设备型式认可，也不修改 Mid-MPC、Threat Management 或 planner 的安全阈值。雷达显示重构完成后，仍需将 raw radar、检测、融合和 COLAV 安全结论分别报告。

## 需要冻结的参数/默认建议

真正需要用户后续确认的只有两项，且都不应阻塞 P0 同源修复：

1. **硬件 profile 锚点（未冻结）**：采用 Furuno 类 12/25 kW 开式 X-band（9410 MHz、24/48 rpm、约 1.9°/1.35° H beam、20° V beam），还是另建紧凑固态 25 W 级 profile。P0 先使用显式 `engineering_xband_v1` profile，并标注“非特定硬件”；硬件型号确认后再冻结 profile provenance。
2. **第一阶段输出规格（未冻结）**：建议 P0 先交付同源稀疏 `RadarScanPacket`，P1 再交付 `2048 × 1024 uint8` polar grid/binary chunks。两者都是工程输出选择，不是真机分辨率指标；选择未确认也不妨碍先修复 packet/source/scan_seq 边界。

以下是建议默认值，不要求另行批准，后续可按 profile 演进：

- 显示：RADAR 默认 raw video + detections；TRACKS/AIS/ENC 作为独立开关。
- 方向：P0 使用 packet 的 yaw 做 head-up 方向；north-up、course-up、pitch/roll 稳定化放入 P2。
- 杂波：P0 沿用当前快速点过程作为开发档，明确“非真机标定”；P1 再加入 K/3MD/He-2024 profile。
- 校准：有真实 X-band spoke/PCAP/视频后进入 P3；此前只做统计仿真验收，不称为真实雷达回放。

## NTNU milliAmpere 选型附录

### 已确认的船和雷达证据

| 平台/时间 | 一手证据 | 雷达结论 | 不能推出的内容 |
|---|---|---|---|
| milliAmpere1，2017 建造；2022 NTNU/IOP 论文 | 论文称船长 5.0 m、宽 2.8 m、air draft 3.3 m；传感器是“marine FMCW X-band radar”，外感传感器装在 roof 上方中央。[本地全文 `milliampere1.txt:85-94,126-172`](../../docs/research/2026-09-30-mass-situational-awareness/research-materials/txt/milliampere1.txt)；[NTNU Open 条目](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/3039489?locale-attribute=en&show=full) | 2017–2022 的公开论文只确认 FMCW、X-band、roof rig | 没有公开型号、频率、功率、rpm、HBW、VBW、脉宽或真实雷达天线相位中心；不能把 Simrad 4G 参数倒灌成 mA1 2022 参数 |
| milliAmpere1，2025 硬件/软件更新论文 | OMAE2025 论文的传感器章节明确写出“maritime radar installed is the HALO24, Simrad”，并在摘要说明 2024 年做过 thruster/electrical upgrade。[论文 DOI](https://doi.org/10.1115/OMAE2025-155401)；公开作者 PDF 文字证据含 HALO24、24-inch dome、48 nm、up to 60 RPM | 这是目前最具体的 mA1 雷达型号证据：Simrad HALO24；可称为 2025 论文所描述的 onboard/current profile | 论文没有证明 HALO24 是 2024 电气升级时才更换；不能把“2024 upgrade”写成“雷达升级年份”；仍没有 mA1 实船雷达原始记录 |
| milliAmpere2，2021 建造/2022 trial；2025 ASME 论文 | Table 2 明确写出“Maritime X-band radar (Simrad Halo 24)”；论文称 2022 trial 的 SITAW 使用 radar+l idar，后来同年另有 camera-only COLAV 实验。[本地全文 `The Autonomous Urban Passenger Ferry milliAmpere2- Design and Testing.txt:107-121,275-296,323-344`](../../docs/research/2026-09-30-mass-situational-awareness/research-materials/txt/The%20Autonomous%20Urban%20Passenger%20Ferry%20milliAmpere2-%20Design%20and%20Testing.txt)；[NTNU 作者手稿](https://torarnj.folk.ntnu.no/MilliAmpere2_paper_final_manuscript_JOMAE.pdf)；[ASME DOI](https://doi.org/10.1115/1.4067370) | mA2 的公开硬件型号也是 Simrad HALO24；船长 8.65 m、宽 3.5 m、draft 0.3 m、air draft 3.5 m，A-frame 顶部 sensor rig | 论文没有声称 2022 后换成另一家雷达；“camera-only”是实验传感器子集，不是雷达硬件更换 |

当前可避免的两种误读：

- **Simrad 4G** 出现在 Autosea/其他 NTNU 雷达跟踪项目的资料中；本地补充档明确这些参数“不属于 milliAmpere1 当前实现”。它不能替代 mA1 2025 论文或 mA2 Table 2 的 HALO24 证据。[`docs/research/2026-09-30-milliampere-sa/2026-09-30-milliampere-sa-01-core-tracking-supplement.md:35-47`](../../docs/research/2026-09-30-milliampere-sa/2026-09-30-milliampere-sa-01-core-tracking-supplement.md)
- **RFbeam K-MD2 24 GHz** 出现在 NTNU 2023 “Real-Time Vessel Detection and Velocity Estimation in Trondheim Harbor” thesis；其目标是向 mA2 通知 Ravnkloaløpet 隧道来船，是港口/岸基辅助雷达项目，不是 mA2 onboard X-band HALO24，应从船载 profile 排除。[NTNU Open thesis](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/3081339)

公开资料没有发现 mA2 的第二个 onboard radar manufacturer，也没有理由用 AIS 设备型号替代雷达型号。Furuno 只是本项目的通用商用 X-band 对照 profile，不是 milliAmpere1/2 的已证设备。

### Simrad HALO24 可用工程 profile

以下值来自 Simrad 官方 HALO24 产品页和官方安装手册；值分为“厂商公开值”和“本项目工程选择”，不把后者写成设备指标。

| profile 字段 | `simrad_halo24_v1` 建议值 | 证据/边界 |
|---|---:|---|
| band | X-band | Simrad 官方产品页/安装手册 |
| transmitter frequency | 9.4–9.5 GHz | 官方 Halo24 installation manual；[Simrad 官方产品页](https://www.simrad-yachting.com/en-sg/simrad/type/radar/halo24-simrad-radar/) |
| transmitter type | solid-state, pulse-compression；无 magnetron、InstantOn | 官方安装手册；产品页确认 pulse compression |
| peak output | 25 W | 官方安装手册；产品页只列功耗，不应拿 20/29 W 功耗当 RF peak power |
| rotation | 20–60 rpm，取决于 mode/range；官方产品页明确 ≤1.5 nm 可 60 rpm | 官方产品页/安装手册；6 nm 下的确切 rpm mapping 未公开 |
| H beam | 3.9° nominal (-3 dB)；target separation high 约 2.0° | 官方安装手册/产品页；2.0° 是 target-separation processing，不等于物理天线主瓣 |
| V beam | 22° nominal (-3 dB) | 官方安装手册/产品页 |
| polarization | horizontal | 官方安装手册 |
| range | product page: 48 nm max, 50 m minimum displayed scale；manual: 100 m–48 nm 18 scales, raw minimum 6 m | 官方产品页与安装手册存在显示/规格口径差异，profile 必须保存 `source_document`，不能自行合并为一个数 |
| pulse/PRF | pulse length 0.04–64 μs ±10%，sweep repetition 700–2400 Hz，max sweep bandwidth 48 MHz | 官方安装手册；pulse compression 下不能单用脉宽声称最终 range discrimination |
| sidelobe/noise | sidelobe <−18 dB within ±10°、<−24 dB outside；noise figure <5 dB nominal | 官方安装手册 |
| physical antenna | 24-inch dome，约 610 mm diameter × 225 mm height，约 6.75–6.9 kg | 官方产品页/安装手册 |

厂商一手页面：[Simrad HALO24 官方产品页](https://www.simrad-yachting.com/en-sg/simrad/type/radar/halo24-simrad-radar/)。频率、峰值功率、脉宽、sweep repetition、旁瓣和噪声 figure 取自 [HALO20/20+/24 官方安装手册（Navico/Simrad PDF）](https://softwaredownloads.navico.com/Simrad/SimradYachting_Software%20-%20Copy/Downloads/documents/Halo_20-20-24_IM_EN_988-12307-005_w.pdf)；该 PDF 直接 fetch 可能不稳定，字段已在本次调研检索结果和本地 profile 表中保留来源边界。

推荐 profile 初值：

```yaml
id: simrad_halo24_milliampere_v1
hardware_anchor: Simrad HALO24
band: X
frequency_ghz: [9.4, 9.5]
transmitter: solid_state_pulse_compression
peak_power_w: 25
horizontal_beamwidth_deg: 3.9
target_separation_high_deg: 2.0
vertical_beamwidth_deg: 22.0
polarization: horizontal
rpm_policy: range_dependent_unknown_mapping
engineering_default_rpm: 24.0
range_scales_nm: [0.75, 1.5, 3, 6, 12, 24]
range_scale_default_nm: 6
antenna_height_m: 3.5
antenna_height_provenance: mA2_air_draft_upper_prior_not_phase_center
range_resolution_m: null
range_cell_pitch_m: null
```

`antenna_height_m=3.5` 只是贴近 mA2 air-draft 的工程先验，不是已测相位中心高度；mA1 可用 3.3 m air-draft 作为另一个先验。两船论文都只证明 top-mounted sensor rig/air-draft，不给雷达天线安装点的精确水面高度。profile 应允许 `antenna_height_m=null`，在未确认时显式使用 scenario prior，不把 12 m 当前默认值称为 NTNU 实船值。

这个 profile 比 Furuno 12/25 kW 开式雷达更贴近当前模拟器的目标：小型 5–8.65 m 研究渡船、圆顶固态雷达、25 W、24/60 rpm 档位、约 6 nm 默认仿真量程、当前已有 `RadarXBand`/PPI 接口。`range_resolution_m` 不应从厂商 pulse length 直接填写；应先根据 pulse-compression processing 或实测/厂商 range discrimination 确认。`range_cell_pitch_m` 是本项目 P1 输出预算字段，建议先按 2048×1024 grid 工程选择，标记为 `engineering_choice`。

### 选型结论和证据边界

推荐使用 `simrad_halo24_milliampere_v1` 作为当前实现的第一个具体 profile：mA1 的 2025 硬件论文和 mA2 的 2025 设计论文都指向 Simrad HALO24，且官方资料给出足够的 X-band、固态、脉冲压缩、波束、转速和量程锚点。mA1 2017–2022 公开论文只给 generic FMCW X-band，因此历史 mA1 早期 profile 仍应标作 `milliampere1_legacy_xband_unknown_v0`，不要回填 Halo24 到早期记录。

目前没有 NTNU milliAmpere 的原始 HALO24 spoke、video/IQ、Pfa/Pd、天线相位中心测量、实际 rpm↔range mapping 或海况标定记录。故 P3 只能完成：profile 参数核验、标定工具、synthetic sweep/CFAR/回放一致性测试、厂商规格对照；不能声称已经完成真机雷达校准，也不能把本地 paper 的硬件型号证据误写成真实回波校准证据。

## 参考和现状证据

- 本仓库 X-band 参数/模型：`colav_simulator/core/sensing.py:475-965`。
- 当前场景装配：`scenarios/head_on.yaml:33-46`。
- tracker/融合接线：`colav_simulator/core/tracking/trackers.py:571-692`；`colav_simulator/integrations/vimmjipda_existence.py:38-105`。
- 仿真循环和量测缓存：`colav_simulator/simulator.py:395-427,606-633`。
- Web PPI：`web_gui/modules/radar-ppi.js:1-19,96-223`。
- Web 旧 RADAR：`web_gui/modules/radar-mini-map.js:12-40`。
- telemetry descriptor/transport：`gui_server/main.py:182-231,1498-1522,1863-1868,2510-2572`。
- Unity 真值雷达原型：`sango/Assets/Scripts/Runtime/RadarOverlay.cs:8-15,112-135`。
- Unity 原始帧与 twin 边界：`sango/Docs/contracts/frame-publisher-v1.md:1-71`；`sango/Docs/contracts/twin-bridge-v1.md:1-10,28-43`。
- SFD 传感器/融合契约：`sango/Docs/contracts/sensor-model-v1.md:1-120`。
- 本地领域背景（雷达处理链、海杂波、spoke/检测/跟踪分阶段建议）：`docs/research/2026-09-30-mass-situational-awareness/02-radar-detection-tracking.md:81-107`。
- NTNU milliAmpere1 原始证据：`paper/milliAmpere- An Autonomous Ferry Prototype.pdf`；文字版 `docs/research/2026-09-30-mass-situational-awareness/research-materials/txt/milliampere1.txt:85-94,126-172`；NTNU Open 条目 `https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/3039489?locale-attribute=en&show=full`。
- NTNU milliAmpere2 原始证据：`paper/The Autonomous Urban Passenger Ferry milliAmpere2- Design and Testing.pdf`；文字版 `docs/research/2026-09-30-mass-situational-awareness/research-materials/txt/The Autonomous Urban Passenger Ferry milliAmpere2- Design and Testing.txt:107-121,248-296,323-344`；NTNU 作者手稿 `https://torarnj.folk.ntnu.no/MilliAmpere2_paper_final_manuscript_JOMAE.pdf`。
- mA1 2025 硬件/软件更新证据：ASME OMAE2025-155401，DOI `https://doi.org/10.1115/OMAE2025-155401`；公开作者稿中明确 HALO24，但是否在 2024 电气升级时更换雷达未知。
- 排除项：NTNU 2023 RFbeam K-MD2 thesis `https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/3081339` 是港口/岸基辅助雷达（24 GHz），不是 mA2 onboard X-band；Autosea Simrad 4G 只属于其项目，不能充当 milliAmpere 型号证据。
- 外部规范：IMO MSC.192(79) §§5.2、5.5、5.10.1、5.11、5.25、5.28、5.30、5.35；量程环准确度、短程 discrimination、AIS/雷达关联和多源处理来源必须按章节分别解释。
- 外部设备 profile：Furuno FAR-15x3 官方规格 PDF（本次调研已读取其中的 9410 MHz、12/25 kW、1.9°/1.35°、20°、24/48 rpm、25 m、1%/10 m、±1° 等字段；官方 PDF 链接偶发 fetch failure，后续需保留原始文件校验）。[Furuno Radar Basics](https://www.furuno.com/en/technology/rader/basic/index.html) 作为可访问的官方原理补充。
- 外部集成仓库：`/Users/marine/Code/ecosystem/vimmjipda`，当前 commit `58e4903`；当前工作树 clean，但 handoff 标注尚未 push。该 Git 状态不构成雷达或融合资格完成证据。
