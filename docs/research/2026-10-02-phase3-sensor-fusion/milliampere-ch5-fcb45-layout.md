# 阶段3 传感器套件域：milliAmpere 第5章蓝本 → 45m FCB 传感器布局与数据需求档案

> 调研日期 2026-10-02；信度标注 [高/中/低/线索]
> 定位：阶段3（船载 X 波段雷达 / 激光雷达点云 / 白光+红外摄像头 / AIS 显示四类传感器模型）的**船型侧需求档案**。以 milliAmpere1 论文（Brekke et al. 2022, J. Phys.: Conf. Ser. 2311 012029，本地 `paper/` 全文）+ 库内既有调研（2026-09-30 两系列、2026-09-29 两份）为基础，围绕本船 45m FCB（`sango/Assets/Art/Purchased/fcb45`）给出传感器分布提案、覆盖分析、仿真参数表与融合管线输入契约草案。
> 坐标约定：后端 NE 米制 / UTM 48N（新加坡海峡）；传感器量测按惯例落 ownship NED（见 §6 契约的显式声明要求）。

---

## ① 参考文件验尸结论（milliampere1.pdf）

| 文件 | `file` 判定 | 内容 | 结论 |
|---|---|---|---|
| `docs/research/2026-09-30-mass-situational-awareness/research-materials/tmp/milliampere1.pdf` | **HTML document**（14,375 字节，无 `%PDF-` 头） | `<title>Radware Bot Manager Captcha</title>` + 混淆 JS + hCaptcha 挑战逻辑 | **废页，不是论文**。是下载时被 Radware 反爬墙截获的验证码页面，不含 milliAmpere 论文任何一节内容。**禁止把此文件当论文引用。** |
| 同目录 `auestad.pdf` | HTML document | NVA（nva.unit.no）单页应用外壳，无正文 | 同为废页（这与库内 `resolve_01.md` 已记录的"Auestad 2021 全文取不到、1.75 m 归属存疑"结论互相印证） |
| 同目录 `linatrine.pdf` | 真实 PDF（9.2 MB）+ 已提取 `linatrine.txt` | NTNU 硕士论文 Theimann & Olsen《Stereo vision for autonomous ferry》（2020-06，导师 Edmund F. Brekke） | **真文献**，是 resolve_01 消解立体基线 1.80 m 的一手全文 |

**milliAmpere 论文正文的正确库内出处**：`paper/milliAmpere- An Autonomous Ferry Prototype.pdf`（16 页），全文逐页提取件 `docs/research/2026-09-30-mass-situational-awareness/research-materials/txt/milliampere1.txt`（行号可复核）。传感器章节（论文第 3 节传感器表 + §5 态势感知全章）由该提取件与两份调研系列覆盖，见 §2。本档案全部 milliAmpere 引用以该提取件为准。

## ② 库内调研提炼（不重做，只引与提炼）

### 2.1 milliAmpere1 传感器事实（一手：`research-materials/txt/milliampere1.txt`）

| 项 | 内容 | 出处（提取件行号） |
|---|---|---|
| 本征传感器 | 双天线 RTK GNSS-compass（内置陀螺稳定）+ 独立 IMU（集成 GNSS/磁力计/气压计）；alpha-beta 滤波出平滑 6-DOF 位姿 | 行 165-170、198-202 |
| 外感传感器 | FMCW X 波段雷达 + Velodyne VLP-16 激光雷达 + 定制桅架（5×Point Grey Blackfly 光学 + 5×FLIR Boson 红外）；**全部外感传感器置于顶棚上方、艏艉与两舷的中点**（环形布置） | 行 170-173 |
| 论文未披露 | 雷达型号/天线高/转速/量程档、相机镜头 FOV、桅架精确高度——论文只给类别，不给规格 | 全文核对（§3 传感器表仅列类别） |
| 处理链 | 陆地过滤（本地笛卡尔系 + Kartverket 地图）→ single-linkage 聚类 → 凸包+质心 → IPDA 融合跟踪（存在概率确认才交运动规划） | 行 369-388 |
| 相机管线 | Bayer 原图 → 千兆以太网 → 彩色化/去畸变 → YOLO v4 检测（bbox+类别）；红外灰度同管线；georeferencing（相机高于海面三角化测距）补距离后同套陆地过滤 | 行 396-417 |
| 立体视觉 | 双机基线论文写 1.75 m/~80 m，库内消解定案：**1.80 m 为一手确证**（硕论实测 1800.25 mm）、注视点 50 m、80 m 外误差超 20 m → 立体按 1.80 m 套件 + 80 m 置信门控 | `05-visual-ir-perception.md` §2.3（C1 定案） |
| milliAmpere1 尺度参照 | LOA 5.0 m、空气高（air draught）3.3 m——5 m 小艇的"桅顶"仅 3.3 m；本船 45 m 的等效布局高度完全不同，不能平移 | 提取件 Table 1（行 120-140） |

### 2.2 各领域报告对布局有约束力的结论（引路径）

| 来源 | 对本档有用的结论 |
|---|---|
| `2026-09-30-mass-situational-awareness/02-radar-detection-tracking.md` | 雷达真实链 8 步；仿真最小补齐集 = **RCS + 海杂波 + 异步漏检**（Gemini σ=1 是低标）；spoke 数据形态对齐 mayara/OpenBR24 生态（Navico BR24/3G/4G/HALO、Raymarine Quantum、Furuno DRS-NXT 已被开源栈支持）→ 仿真雷达选型优先 Navico 族；杂波分布选型锚点（X-band KR 0.30 dB / 3MD 0.11 dB，CCDF=10⁻⁴ 口径）；量测噪声 diag(2²–6²) m 分级 |
| `.../03-lidar-slam.md` | 仿真 lidar 最小保真度基线 **≥10 Hz、16 线、~100 m 量程**（VLP-16 数据条件）；可靠关键点半径约 30 m；z 轴漂移 22-54 m 是船载 lidar 通病 |
| `.../04-multi-sensor-fusion-ipda.md` | 测量级融合（单跟踪器吃全部点检测）是两条实地线共同选择；**Autoferry SFD 格式** = sensorID（Lidar:1/Radar:2/IR:3/EO:4）+ Unix 时间戳 + ownship-NED 量测数组（EO/IR 1×M 方位；Lidar/Radar 2×M 北东）+ 量测时刻 ownship 位置；VIMM 标定噪声 σ_r=8 m、σ_θ=1.0°、σ_c=6.6 m；可见性链 ω₁₁=0.90、ω₀₁=0.52；杂波 5×10⁻⁷/m²、新目标 10⁻⁷/m²；PD=92%；确认/终止阈值 Tc=99.9%/Td=1%/6 拍；vimmjipda 为**外部仓库集成**（`~/Code/ecosystem/vimmjipda`，registry 动态加载），本仓库距融合在环只差量测流生成器；AIS 进融合器是开放问题（仅定性验证） |
| `.../05-visual-ir-perception.md` | FLIR Boson：320×256/640×512、8-14 μm LWIR、60 Hz（averager 开 30 Hz）、启动 2.5-3 s、FFC 机制；相机检测概率环境绑定（城区 EO 0.78 vs 开阔 0.51，lidar 0.92）；georef 后跟踪建立率优于雷达但位置 RMS 变差（8.15-9.45 m vs 7.45 m）；渲染需求 = 雾/昼夜/水面倒影/海天线/水线；IR 特有 = AGC/FFC/海天结构杂物 |
| `.../06-simulation-digital-twin.md` | Gemini 已归档（2022-02），PyGemini 无代码；MSS 是唯一活跃可复用底盘；**RCS+杂波注入是公开领域空位**；lidar 几何级成熟（30M pts/s @ 50 fps 路线）；IR 是全行业短板（artistic emissivity） |
| `.../07-confidence-aware-colav.md` | ECC19 门控先例：存在概率超阈值才输出 `{ID, pN, pE, u, χ}` 给 MPC；工程接口普遍无置信度字段；F0-F7 字段表挂融合器输出接口 |
| `.../01-navigation-geodesy.md` | 双天线 GNSS-compass 航向误差 θ_err ≈ P_err/L（毫米级相对定位 + 1 m 基线 ≈ 0.05-0.1°）→ **基线越长航向越准**；RTK fix 态 cm 级是条件精度；失锁恢复跳变 >1 m；NED/ENU 坐标约定分裂是常见坑 |
| `2026-09-29-sensor-fusion-hardware-survey.md` | 行业收敛 = **雷达+AIS+GNSS 底座、相机/红外补盲、LiDAR 近距**（LiDAR 非必需）；NTNU autoferry 是唯一四需求全覆盖学术平台；SOLEIL 红外双焦段（tele ~2 km + wide 近距）靠离泊；Wärtsilä IntelliTug 近场雷达+LiDAR+相机融合；DTU 蓝图 = 全以太网 + 高吞吐传感器独立子网 + GNSS 硬件时间源；raw radar 接口坑（Navico 私有 UDP 靠社区逆向） |
| `2026-09-29-dt-sensor-replay-paper-survey.md` | `sensing.py` 现状缺口：雷达无陆地遮挡与海况杂波物理、AIS 只有报告率无延迟/龄期、无相机类；雷达杂波用 Angelliaume 2019（定参）+ He 2024（生成）配套替换 i.i.d. 泊松 |
| `2026-09-30-milliampere-sa/*-pipeline-report.md` | vimmjipda 存在概率在跟踪器内完整，但**接口/数据模型/决策三层断路**；ma2 全部传感器经 SenTiBoard 精确打标同步；ma2 传感器表 = RTK GPS compass（cm 级）+ 备份 GPS + X-Sens IMU；雷达 spokes 用导航数据聚合为全局点云后 map-based filtering |

### 2.3 FCB45 本船尺度（一手锚）

| 项 | 数值 | 出处 |
|---|---|---|
| LOA / Lpp | 45.00 m / 44.10 m | `docs/research/2026-09-20-45m-fcb-model-calibration-feasibility.md`（规格书 REV T + Data Sheet）；`sango/Assets/Art/Purchased/fcb45/PROVENANCE.txt` |
| 型宽 / 型深 | 8.00 m / 3.85 m（自基线） | 同上（两处一致） |
| 设计吃水 / 最大吃水 | 1.55 m / 2.00 m | 同上；后端 `colav_simulator/modular_gnc/fcb45_environment.py` L150-152（44.1/8.0/2.0） |
| 服务航速 | 25 kn @ 30 t DWT、100% MCR（≈12.9 m/s）；最低服务 18 kn | 同上 |
| **空气高（模型实测）** | **12.98 m**（设计水线上）；顶点在中纵剖面、舯前约 +2.1 m（桅杆顶）；龙骨 −1.97 m 与最大吃水 2.00 m 吻合（模型姿态自校验通过） | 本档对 `sango/Assets/Art/Purchased/fcb45/source/FCB45_Unity.fbx` 的二进制顶点解析（FBX 7400，15 个 mesh，原点=舯剖设计水线；交付 README 声明 +Z 艏） |
| 既有航行设备（同型官方页） | 1× X 波段雷达、AIS、GPS、测深仪、自动舵、磁罗经、海图机、风系统、2× 探照灯、GMDSS A1+A2；2× 10 kN 艏侧推、DP1、BV 入级 | BlueGen Marine 45m FCB 页（§3），全部船东文档数字逐项吻合（LOA/LBP/型宽/型深/吃水/3×KTA-38-M2/REINTJES 3.048 PTO-PTI/85 客位） |

桅杆精确高度最终以船东总布置图为准；本档以模型实测 13.0 m 空气高为基准，雷达天线工作高度取 **12 m**（桅顶 13.0 m 减灯杆/天线余量），并给 8/10/12 m 三档参数化表兜底。

## ③ 联网补缺（库内没有的，带 URL）

| # | 事实 | 数值/规则 | 来源与信度 |
|---|---|---|---|
| W1 | 雷达天线安装盲区规则（IMO） | 天线位置应使障碍盲区**不落在船艏正前至两舷正横后 22.5° 弧内**；单个盲区 >5°、合计 >20° 应尽可能避免 | IMO SN.1/Circ.271（2008-05-22）官方 PDF，[imo.org](https://wwwcdn.imo.org/localresources/en/OurWork/Safety/Documents/IMO%20Documents%20related%20to/SN.1-Circ.271.pdf)；高 |
| W2 | 雷达地平公式 | d(nm) ≈ 2.2×(√h₁+√h₂)，h 单位米（4/3 等效地球半径折算系数；总探测距离=本船地平+目标地平） | [Wikipedia: Radar horizon](https://en.wikipedia.org/wiki/Radar_horizon)、[OceanCalc](https://oceancalc.com/tools/radar-horizon-calculator)、[Starpath](https://www.starpath.com/cgi-bin/web_card/courses/glossary.pl?show_def=287&cat=)；高（教科书级通式） |
| W3 | 近距环形盲区 | R_min ≈ h_ant / tan(VBW/2)（垂直波束下缘掠过天线高度处起才能照到水面）；脉冲盲区 c·τ/2 短脉冲≈12 m 量级，次要 | 几何通式（GB/T 与雷达工程手册通用作法）；公式高、VBW 取值中 |
| W4 | VLP-16 官方规格 | 16 线、量程至 100 m、垂直 FOV ±15°（30°）、水平 360°、5-20 Hz、单回波约 30 万点/s（双回波约 60 万）、905 nm、8 W | [Ouster VLP-16 官方页](https://ouster.com/products/hardware/vlp-16)、[Puck spec sheet Rev F](https://www.hypertech.co.il/wp-content/uploads/2015/12/63-9229_Rev-F_Puck__Spec_Sheet_Web.pdf)；高 |
| W5 | 24 in 圆顶雷达典型规格（HALO24） | 48 nm 最大量程；**60 rpm（≤1.5 nm 近距档）/ 24 rpm（远距档）双模式**；20 W；24 in 圆顶 | [Simrad Commercial HALO24](https://www.navico-commercial.com/simradcommercial/series/halo-dome/halo24simrad24radar-c82d7cbc)、[Simrad](https://www.simrad-yachting.com/simrad/type/radar/halo24simrad24radar)；高；垂直波束宽官方页未公开，圆顶类典型 20-25° 取值按中置信处理 |
| W6 | 海事双光谱云台相机（白光+红外一体） | FLIR M625CS：640×512 LWIR（25°×19°）+ 白光 36× 光学变焦、360° 连续水平、±90° 俯仰、两轴陀螺稳像；M618CS（18°×14° LWIR，35 mm 焦距）厂商/零售页宣称对**小艇探测 >2 n mile** | [West Marine M625CS](https://www.westmarine.com/flir-m625cs-thermal-camera-system-with-gyro-stabilization-and-color-camera-18424036.html)、SourceSecurity M618CS datasheet（零售/厂商页级）；规格高、"2 n mile 小艇探测"中置信 |
| W7 | 同型 45m FCB 官方参数页（本船数字源） | LOA 45.00/LBP 44.10/宽 8.00/深 3.85/设计吃水 1.55/最大 2.00/25 kn@30t/3×Cummins KTA-38-M2/REINTJES PTO-PTI/2×10 kN 艏侧推/DP1/BV/85 客位 + 既有航行设备清单（见 §2.3） | [BlueGen Marine – 45m Fast Crew Boat](https://bluegenmarine.com/fast-crew-boat)，与船东两份文档（规格书 REV T、Data Sheet）逐项一致；高（同型官方页，非本船图纸） |

**未检索到的缺口（明示）**：45 m 级 FCB 桅杆高度的船级社/行业统计惯例（无公开汇总文献，用同型官方页 + 本船模型实测替代）；FLIR M 系官方 datasheet 全文（零售页转述）。

## ④ FCB45 传感器布局提案（核心产出）

### 4.1 布置总图（文字版）

```
  侧视（艏右）          h≈12.0 m  ┌─ X 波段 24in 圆顶天线（中纵剖面，桅顶）
                                ├─ 双光谱陀螺稳像云台（白光 36× + 640×512 LWIR，桅顶前伸托架）
        桅杆(x≈+2m)   h≈10.5 m  ├─ EO 环视 5× 固定白光（桅围栏圈，80° HFOV×5 → 360°）
        雷达桅          h≈10.5 m  ├─ IR 固定 4×（艏/艉/左/右，90° HFOV）
        GNSS 前天线    h≈11.5 m  ├─ GNSS-compass 前天线（桅杆顶部中纵剖面）
        LiDAR          h≈11.0 m  └─ 360° 激光雷达（桅顶下法兰，避开雷达波束近场）
  驾驶室顶 h≈6-7 m（估算，待 GA 图确认）
  主甲板   h≈+2.3 m（型深 3.85 − 设计吃水 1.55）
  水线     0（设计吃水 1.55 m）；龙骨 −1.97 m（模型实测）
        艉部(x≈−20m)   h≈+3 m    GNSS-compass 后天线（艉甲板中纵剖面短杆）→ 基线≈22 m
                                 IMU（舯剖设计水线处，C.G. 就近）
```

所有角度敏感设备同桅集中（与 milliAmpere「全部外感传感器置于顶棚上方、艏艉/两舷中点」同构），保证 EO/IR/LiDAR 外参共桅、一次性标定；GNSS-compass 双天线沿中纵剖面拉开基线。

### 4.2 分设备布置表

| 设备 | 安装点（x=纵向，0=舯剖，+艏） | 高度（水线上） | 关键参数 | 布置理由 |
|---|---|---|---|---|
| **X 波段雷达** | 桅顶中纵剖面，x≈+2 m | **12.0 m**（参数化 8/10/12） | 24 in 圆顶（HALO24 级）；24 rpm（远档 6-48 nm）/ 60 rpm（近档 ≤1.5 nm）；量程档 0.25/0.5/1/3/6/12/24(48) nm；HBW≈5°、VBW 20-25° | ①中纵剖面圆顶 → 障碍盲区≈0°，满足 SN.1/Circ.271「艏正前至两舷正横后 22.5° 无盲区」（W1）；②24 in 圆顶是 mayara/OpenCPN/OpenBR24 开源生态全覆盖的最低成本入口（报告 02 §2.4）；③60 rpm 近距档直接服务避碰（W5） |
| **LiDAR（点云视角）** | 桅顶雷达下方法兰，x≈+2 m | **11.0 m** | 基线配 16 线/±15°/360°/10-20 Hz/100 m（VLP-16 级）；升级位留 32-128 线 200 m 档 | ①桅顶最高可见点之下、雷达之上，360° 无自遮挡（驾驶室顶 h≈6-7 m 在其下方）；②报告 03 的最小保真度基线（16 线/10 Hz/100 m）；③海峡闭合速度下 100 m 只够近距，见 4.3 覆盖分析——升级档按需 |
| **白光相机 ×5（固定环视）** | 桅围栏圈均布 5 点（艏 0°、两舷 144°/216°、艉 288°/72° 各偏 36°错位） | 10.5 m | 80° HFOV×5、15° 重叠 → 360° 覆盖；1080p、30 fps、raw Bayer 千兆网（milliAmpere 管线同构） | milliAmpere 5×Blackfly 环形布置的等比移植（其 5 m/3.3 m 船 → 45 m/10.5 m 桅）；被动通道供类别与方位（georef 进同一跟踪器） |
| **红外相机 ×4（固定）** | 艏 0° / 左舷 90° / 右舷 270° / 艉 180° | 10.5 m | 640×512 LWIR（Boson 级：8-14 μm、60/30 Hz）、HFOV 90° | 新加坡海峡夜航与渔船/小艇热信号刚需（PoLaRIS：热像=夜间检测刚需；09-29 硬件档）；比 milliAmpere 5× 少 1 台（前向由云台补.tele）省带宽/功耗 |
| **双光谱云台 ×1** | 桅顶前伸托架（雷达圆顶前下方），x≈+2.5 m | 11.5 m | 白光 36× 变焦 + 640×512 LWIR（M625CS 级）；360° 水平、两轴稳像 | ①远距类别辨认（SOLEIL tele/wide 双焦段先例，09-29 硬件档）；②对雷达/lidar 疑似点做按需视轴引导（PTZ 指向目标方位）；③稳像抵消 25 kn 残余振动 |
| **GNSS-compass 双天线** | 前：桅顶中纵剖面 x≈+2 m；后：艉甲板短杆 x≈−20 m | 11.5 m / 3.0 m | 基线≈22 m → 航向噪声≈0.013°（5 mm/22 m 换算，报告 01 公式）；RTK fix cm 级 + 备份单 GPS（ma2 同构：Table 2 备份 GPS 接 DP） | 基线越长航向越准（报告 01 §2.1）；前后天线连线即艏向基准，无需陀螺粗对准 |
| **AIS** | VDL 接收天线桅杆副桅（任意高位） | ≥11 m | 数据源=后端既有海峡 AIS 流；传感器模型只做**报告率+延迟/龄期+位置噪声**退化注入 | 用户指定"数据显示"定位；09-29 DT 档已标注 sensing.py 缺口；暂不进融合器（报告 04 开放问题 5） |
| **IMU** | 舯剖设计水线上方舱内（C.G. 就近） | ≈0 | 6 轴 + 内置 GNSS/磁力计/气压计（ma1 同构） | 本征链路：alpha-beta/EKF 出 6-DOF 位姿，全部外感量测落系统一坐标系 |

### 4.3 覆盖分析（45 m 船尺度下的近距盲区与雷达阴影）

**雷达**

| 项 | 公式 | h_a=8 m | h_a=10 m | **h_a=12 m（基准）** |
|---|---|---|---|---|
| 地平（目标自由board 2 m 小艇） | 2.2(√h_a+√2) | 9.3 nm | 10.1 nm | **10.7 nm** |
| 地平（8 m 拖轮/渔船） | 2.2(√h_a+√8) | 12.3 nm | 13.2 nm | **13.8 nm** |
| 地平（20 m 干舷大船） | 2.2(√h_a+√20) | 16.1 nm | 16.8 nm | **17.5 nm** |
| 地平（35 m 干舷集装箱/VLCC） | 2.2(√h_a+√35) | 17.8 nm | 18.7 nm | **20.6 nm** |
| 近距环形盲区（VBW 25°） | h/tan12.5° | 36 m | 45 m | **54 m** |
| 近距环形盲区（VBW 20°） | h/tan10° | 45 m | 57 m | **68 m** |
| 障碍水平盲区（圆顶中纵剖面） | — | ≈0° | ≈0° | **≈0°**（合规 W1） |

读法：①本船 12 m 天线对 2 m 小艇的几何地平 ≈10.7 nm，但**小目标实际检测是 RCS 限制而非地平限制**（消费级圆顶对玻璃钢艇 2-6 nm 实效），海峡场景主用 6/12 nm 档、 facility 态 24 nm 档；②近距环形盲区 54-68 m 是 12 m 天线高度的物理代价——45 m 船本体的 22.5 m 半长内盲区落在船侧正横近处，**60 rpm 近距档 + LiDAR/相机近距补盲**正是为此冗余；③若改侧装开缝阵（offset 1 m、桅杆 0.3 m 宽）会引入 ≈17° 阴影扇区（2·arcsin(0.15/1.0)），单个 >5° 违反 W1 惯例——提案故取中纵剖面圆顶。仿真可另注入 ≤5° 的桅杆索具阴影作为保真选项。

**LiDAR**（VLP-16 级 16 线，装高 11 m，垂直 ±15°）

- 近场水面盲圈：下缘 −15° 打到水面 = 11/tan15° ≈ **41 m**；0.5 m 出水高小目标最远可见起点 (11−0.5)/tan15° ≈ **39 m**；2 m 自由board小艇 ≈ **30 m** 起。
- 远端：标称 100 m（NOAA 实测 905 nm 对低反射目标实际 50-90 m）。
- **海峡闭合速度核算（本档关键判定）**：本船 25 kn（12.9 m/s）+ 对遇/横交 12 kn（6.2 m/s）→ 闭合 ≈19 m/s；100 m 量程仅给 **≈5.3 s** 预警——对 COLREG 12-15 拍级的跟踪确认（IPDA 6 拍终止规则）勉强，对 6-12 nm 级态势完全不够。**结论：LiDAR 定位=近距补盲与精确几何（<100 m，与雷达近距环形盲区互补），中远距态势由雷达+AIS 承担**——与 09-29 硬件档行业收敛结论一致。若预算允许，升级 32-128 线 200 m 档（OS1/OS2 级）把近距确认窗拉到 ≈10.6 s，属可选档而非基线。

**白光/红外**

- EO 环视 5×80°=400° 名义 → 15° 重叠无死角；IR 4×90°=360° 无死角；云台 360° 全向补.tele 与前向远距。
- georeferencing 测距范围：相机高 10.5 m，水线约束三角化的可用距离由检测分辨率决定——量级上对小艇 0.5-2 km 有效（Helgesen 2022 OE：EO 检测概率城区 0.78/开阔 0.51；"maximum detection range 也 greater than radar"，报告 05 E3/E4），位置量测呈径向拉长（报告 04 E5），只补方位与类别，不做主测距源。
- 立体选项（可选实验位）：1.80 m 基线、注视点 50 m、80 m 置信门控（resolve_01 定案）；装在桅杆横臂两端的可行性由 Unity 模型横臂几何决定，默认不进基线配置。

**AIS/GNSS**

- AIS 覆盖 VDL 20-40 nm 量级（海峡场景后端已供给），只受报告率（随 SOG/转向 2-10 s 量级，ITU-R M.1371 类行为，待按后端 AIS 流实测校准）与龄期限制；GNSS RTK fix 在海峡开阔水域常态可用，桥区/高桅遮挡事件按报告 01 三态模型注入。

## ⑤ 仿真参数需求汇总（供后端 sensor model + Unity 视景分列）

### 5.1 X 波段雷达（spoke 流）

| 参数 | 建议值 | 侧 | 备注 |
|---|---|---|---|
| 天线高 h_ant | 12 m（可配 8/10/12） | 后端+Unity | Unity：模型桅顶挂点（x≈+2 m, y≈12.0 m） |
| 转速 | 24 rpm 远档 / 60 rpm 近档 | 后端 | 扫描周期 2.5 s / 1.0 s；档位随量程联动 |
| 量程档 | 0.25/0.5/1/3/6/12/24/48 nm | 后端 | 量程=距离单元表长度定义 |
| spoke 数/转 | 360-720（1°/0.5° 分辨） | 后端 | 对齐 mayara/OpenBR24 spoke 形态（报告 02 §2.4） |
| 波束宽 | HBW≈5°、VBW=25°（20° 可选） | 后端 | 椭圆主瓣方向图（Gemini spokes equation 骨架） |
| 水平盲区 | 0°（中纵剖面圆顶）+ 可选 ≤5° 索具扇区 | 后端+Unity | Unity 渲染遮挡掩膜用 DEM/场景 raycast（09-29 DT 档方案） |
| 近距盲环 | R_min = h/tan(VBW/2)（54-68 m） | 后端 | 每 spokes 内距离单元置无效 |
| 目标回波 | 船体多散射中心点云（质心可提取、离散度可分解椭圆） | 后端 | 报告 02 §5 表第 5 行；RCS 查表按目标类 |
| 海杂波 | compound-Gaussian（KR/3MD 选型）+ He 2024 SIRP 生成，参数由海况驱动 | 后端 | 报告 02 §2.3（H7 证据链） |
| 缺陷注入 | 概率漏检 + 时间戳抖动（异步） | 后端 | 报告 02 §5 第 7 行 |
| Unity 视觉 | 雷达 PPI 显示画面（量程环、spoke 扫描线、目标回波斑、杂波噪点、盲区扇区） | Unity | 消费后端 spoke 流；HDRP 场景同时供遮挡真值 |

### 5.2 LiDAR（点云）

| 参数 | 建议值 | 侧 | 备注 |
|---|---|---|---|
| 线数/FOV | 16 线、垂直 ±15°、水平 360°（升级位 32-128 线 200 m） | 后端+Unity | Unity：Gemini 式 depth-buffer 柱状拼接（16-128 线可配，报告 06） |
| 装高/挂点 | 11.0 m，桅顶下法兰 x≈+2 m | Unity | 外参与 GNSS/相机共桅标定 |
| 帧率/点密度 | 10 Hz（可 5-20）；约 30 万点/s（单回波） | 后端 | 报告 03 最小保真度基线；VLP-16 官方值（W4） |
| 有效量程 | 100 m 标称（低反射 50-90） | 后端 | 近距水面盲圈 41 m（§4.3） |
| 噪声/退化 | 高斯测距噪声 + 浪致点噪 + 振动畸变 + 雨雾衰减（可配） | 后端 | 报告 03 §5.3（H9：不注入则 SLAM/跟踪评测系统性乐观） |
| Unity 视觉 | 点云可视化（俯视/透视），目标级着色；浪面回波粒子 | Unity | 消费后端点云流或 Unity 直接出点云后端消费（二选一，倾向后端按几何真值生成、Unity 只显示） |

### 5.3 白光 + 红外相机

| 参数 | 建议值 | 侧 | 备注 |
|---|---|---|---|
| EO 阵列 | 5×固定，80° HFOV×5 15° 重叠，1080p@30 fps，raw Bayer | Unity+后端 | 逐相机内参/畸变注入（milliAmpere 管线） |
| IR 阵列 | 4×固定，90° HFOV，640×512@30 Hz（Boson 级 8-14 μm） | Unity+后端 | AGC/FFC 瞬态、启动 2.5-3 s 可选注入（报告 05 E9） |
| 双光谱云台 | 1×，白光 36× 变焦 + 640×512 LWIR，360°/±90°，两轴稳像 | Unity+后端 | 视轴引导接口：目标方位 → PTZ 指向 |
| 挂点 | 桅围栏 10.5 m / 桅顶托架 11.5 m | Unity | |
| 检测层 | bbox+类别（YOLO 系可挂载）或直接给方位量测 | 后端 | georef（相机高+海平面三角化+Sobel/Hough 水线精修）后进同一跟踪器（报告 05 §2.2） |
| 环境域 | 雾/霾浓度梯度、昼夜、水面倒影、海天线 FP、太阳耀斑 | Unity | 报告 05 §5 渲染需求清单；与雷达杂波共享环境分层协议（I4） |
| Unity 视觉 | 桅顶相机实画面（画中画/PIP）+ 检测框叠加 | Unity | 阶段2 像素流已具备承载条件 |

### 5.4 AIS / GNSS / IMU

| 参数 | 建议值 | 侧 | 备注 |
|---|---|---|---|
| AIS 报告率/龄期 | 2-10 s 动态（随 SOG/转向）+ 延迟/龄期噪声注入 | 后端 | 补 sensing.py 缺口（09-29 DT 档）；Unity 侧 AIS 目标列表显示（船位/矢量/标签） |
| GNSS 三态 | RTK fix（cm）/ float（分米-米）/ 单点（米）+ 失锁恢复跳变 >1 m 事件 | 后端 | 报告 01 E7；桥区事件注入 |
| GNSS-compass 航向噪声 | 0.013°（基线 22 m）+ 多径事件 | 后端 | 报告 01 §2.1 公式换算 |
| IMU | 6 轴，含 GNSS/磁/气压计；量测级偏差/漂移可配 | 后端 | ma1 同构 |

## ⑥ 对融合/跟踪管线的输入契约草案

按 Autoferry SFD 格式扩展（报告 04 §2.5），供量测流生成器（当前平台最大缺口）直接实现：

```yaml
# 量测流（逐条消息）
frame_id: "ownship_ned"          # 显式声明；世界系 = UTM 48N NE 米制（后端约定）
                                 # NED/ENU 转换只发生在生成器边界内（报告 01 坐标约定坑）
epoch: unix_ns                   # 单一时间源：GNSS PPS/仿真钟；乱序到达选项保留（OOSM）
sensor_id: 1|2|3|4|5             # Lidar:1 / Radar:2 / IR:3 / EO:4 / AIS:5(扩展,暂不进融合器)
measurements:                    # EO/IR: 1×M 方位(rad)；Lidar/Radar: 2×M NE(m)
  - {azim: ..., }                # AIS: 报文级 {mmsi, lat→NE 投影, sog, cog, timestamp_of_reception}
ownship_pose_at_measurement: {pN, pE, yaw, pitch, roll}

# 每传感器退化参数（生成器配置，锚定 VIMM 标定值）
noise:        {lidar_sigma_c: 6.6, radar_sigma_r: 8.0, radar_sigma_theta: 1.0deg}  # 经雅可比投影（E5 形态）
visibility:   {per_sensor_type markov: {w11: 0.90, w01: 0.52}, global_PD: 0.92, fov_outside_PD: 0}
clutter:      {poisson_rate: 5e-7_per_m2, new_target_rate: 1e-7_per_m2}
async_jitter: {radar_scan_period: 2.5|1.0, drop_p: config}

# 跟踪器侧（vimmjipda，外部仓库集成，registry 加载不可用即抛错）
track_mgmt:   {Tc: 0.999, Td: 0.01, terminate_after: 6}

# 融合器输出 → COLAV（ECC19 门控先例 + 报告 07 F 字段扩展）
confirmed_tracks:
  - {id, existence_prob: r,
     visibility_per_sensor: {lidar, radar, ir, eo},
     pN, pE, u, chi,                      # 位置/速度/航向
     extent: {theta, a, b},               # 可选：椭圆扩展目标（PAKF-JPDA 线）
     class, class_confidence}             # 报告 05：类别先验进避碰差异化建模
```

要点：①AIS 作旁路显示通道，不进融合器（报告 04 开放问题 5 的保守解，后续可升级为量测源）；②EO/IR 为方位量测，georef 在生成器内完成、跟踪器只见同构量测；③存在概率 r 的语义是「虚警预算标定出的门控量」，避碰侧禁止读成目标存在概率真值（报告 07 §2.2）；④本契约即 09-30 收口篇「⑥ 目标列表交付 schema 纯空白」的补位。

## ⑦ Sources

**库内（全部为绝对路径）**

- 论文全文提取：`/Users/marine/Code/Colav-Simulator/docs/research/2026-09-30-mass-situational-awareness/research-materials/txt/milliampere1.txt`（行 120-173 传感器表/布置、行 369-388 处理链、行 396-417 相机管线）
- 废页验尸对象：`/Users/marine/Code/Colav-Simulator/docs/research/2026-09-30-mass-situational-awareness/research-materials/tmp/milliampere1.pdf`（Radware captcha）、同目录 `auestad.pdf`（NVA 壳）
- 真硕论：同目录 `linatrine.pdf` / `linatrine.txt`（Theimann & Olsen 2020）
- `docs/research/2026-09-30-mass-situational-awareness/00-overview.md`、`01-navigation-geodesy.md`、`02-radar-detection-tracking.md`、`03-lidar-slam.md`、`04-multi-sensor-fusion-ipda.md`、`05-visual-ir-perception.md`、`06-simulation-digital-twin.md`、`07-confidence-aware-colav.md`、`08-pipeline.md`；`research-materials/resolve_01.md`
- `docs/research/2026-09-30-milliampere-sa/2026-09-30-milliampere-sa-00-overview.md`、`...-pipeline-report.md`
- `docs/research/2026-09-29-sensor-fusion-hardware-survey.md`、`docs/research/2026-09-29-dt-sensor-replay-paper-survey.md`
- FCB45 尺度：`docs/research/2026-09-20-45m-fcb-model-calibration-feasibility.md`；`sango/Assets/Art/Purchased/fcb45/PROVENANCE.txt`；`sango/Assets/Art/Purchased/fcb45/source/FCB45_Unity.fbx`（本档 FBX 二进制顶点解析：空气高 12.98 m、桅位 +2.1 m、龙骨 −1.97 m）；`colav_simulator/modular_gnc/fcb45_environment.py` L150-152

**外部**

- milliAmpere 论文 DOI：10.1088/1742-6596/2311/1/012029（Brekke et al. 2022）
- IMO SN.1/Circ.271《Guidelines for the installation of shipborne radar equipment》：https://wwwcdn.imo.org/localresources/en/OurWork/Safety/Documents/IMO%20Documents%20related%20to/SN.1-Circ.271.pdf
- Radar horizon：https://en.wikipedia.org/wiki/Radar_horizon ；https://oceancalc.com/tools/radar-horizon-calculator ；https://www.starpath.com/cgi-bin/web_card/courses/glossary.pl?show_def=287&cat=
- Velodyne VLP-16：https://ouster.com/products/hardware/vlp-16 ；https://www.hypertech.co.il/wp-content/uploads/2015/12/63-9229_Rev-F_Puck__Spec_Sheet_Web.pdf
- Navico HALO24：https://www.navico-commercial.com/simradcommercial/series/halo-dome/halo24simrad24radar-c82d7cbc ；https://www.simrad-yachting.com/simrad/type/radar/halo24simrad24radar
- FLIR M625CS：https://www.westmarine.com/flir-m625cs-thermal-camera-system-with-gyro-stabilization-and-color-camera-18424036.html （M618CS 规格转引 SourceSecurity datasheet）
- 同型 45m FCB 官方参数页：https://bluegenmarine.com/fast-crew-boat
