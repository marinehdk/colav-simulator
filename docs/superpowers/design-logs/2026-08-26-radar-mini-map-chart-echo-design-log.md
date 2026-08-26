# 设计日志: RADAR Mini Map 海图与回波融合

> **模式**: 重构        **创建**: 2026-08-26
> **关联 spec**: —
> **状态**: Step-1 进行中

## 0. 决策树状态(权威索引 · 可变快照)

### 0.1 决策点注册表 [DP]

| ID | 描述 | 类型 | 父/分解 | 状态 | 详见 |
|----|------|------|---------|------|------|
| DP-01 | RADAR 卡片的产品身份: 雷达 PPI、ENC Mini Map，还是明确标源的混合显示 | 架构 | — | 未决 | — |
| DP-02 | ENC 上下文渲染技术: 现有 raster tile、safe-water polygons 或新增矢量 SENC 子集 | 技术 | TD-01 | 未决 | — |
| DP-03 | 是否新增静态物标雷达回波模拟，而不是把 ENC 岛屿伪称为雷达探测 | 技术 | TD-02 | 未决 | — |
| DP-04 | 动态目标显示技术: raw truth、Radar measurements、Tracker targets 及 AIS/radar association | 技术 | TD-03 | 未决 | — |
| DP-05 | 探测范围权威: UI 固定 2000 m、执行 RadarParams.max_range 或运行时量程档位 | 接口 | — | 未决 | — |
| DP-06 | ENC、Radar、AIS/Tracker 的坐标、datum、scale、orientation、CCRP 与时间配准 | 约束 | TD-01/TD-02/TD-03 | 未决 | — |
| DP-07 | 图层优先级、透明度、显隐和来源标识，保证 radar/targets 不被 chart 遮挡 | 架构 | TD-01 | 未决 | — |
| DP-08 | 前方 120° 蓝扇区的语义: 注意区而非 360° 雷达传感器视场 | 接口 | — | 未决 | — |
| DP-09 | Risk 框色和目标选择继续消费 canonical Threat Projection，不在 Mini Map 推断风险 | 接口 | TD-03 | 未决 | — |
| DP-10 | chart、radar measurement、heading、position 任一缺失/陈旧时的降级和状态标识 | 约束 | TD-01/TD-02/TD-03 | 未决 | — |
| DP-11 | 240 px 卡片的信息预算: 海岸/岛屿、浅水、航标、航线、回波、目标中哪些默认显示 | 约束 | — | 未决 | — |
| DP-12 | ENC 数据输入和缓存生命周期 | 接口 | TD-01 | 未决 | — |
| DP-13 | ownship-centred ENC 裁剪、投影和圆形 clipping | 算法 | TD-01 | 未决 | — |
| DP-14 | 小尺寸 ENC 几何简化和符号取舍 | 算法 | TD-01 | 未决 | — |
| DP-15 | Chart 图层加载失败时不影响 Radar/target 图层 | 约束 | TD-01 | 未决 | — |
| DP-16 | 静态回波的反射几何与岛岸线数据源 | 算法 | TD-02 | 未决 | — |
| DP-17 | 静态回波视线遮挡、距离衰减和强度模型 | 算法 | TD-02 | 未决 | — |
| DP-18 | 雷达扫描周期、bearing/range 分辨率和时间戳 | 阈值 | TD-02 | 未决 | — |
| DP-19 | sea/rain clutter、漏检、虚警与噪声模型 | 算法 | TD-02 | 未决 | — |
| DP-20 | synthetic radar video/echo 的后端 schema、来源与不可用原因 | 接口 | TD-02 | 未决 | — |
| DP-21 | Radar measurements 到 Tracker target 的关联和去重 | 算法 | TD-03 | 未决 | — |
| DP-22 | 目标航向/速度向量的来源、陈旧阈值和 unavailable 表达 | 接口 | TD-03 | 未决 | — |
| DP-23 | 目标选中、右栏 Risk card 和 Mini Map 符号的双向联动 | 接口 | TD-03 | 未决 | — |

### 0.2 技术分解注册表 [TD]

| ID | 技术 | 分解子模块(→DP) | 触发步骤 |
|----|------|------------------|----------|
| TD-01 | ENC context renderer | 数据源/缓存(DP-12)、投影裁剪(DP-13)、小图简化(DP-14)、独立降级(DP-15)、配准(DP-06)、层级(DP-07) | Step1 |
| TD-02 | Synthetic static radar echo | 反射几何(DP-16)、遮挡/强度(DP-17)、扫描分辨率(DP-18)、clutter/noise(DP-19)、schema/provenance(DP-20)、配准(DP-06) | Step1 |
| TD-03 | Dynamic radar target pipeline | 目标权威(DP-04)、measurement/track association(DP-21)、航向/陈旧(DP-22)、Risk/selection linkage(DP-09/DP-23)、配准(DP-06) | Step1 |

### 0.3 盲区注册表 [BL]

| ID | 问题 | 归属决策点 | 优先级 | 调研状态 |
|----|------|-----------|--------|----------|
| BL-01 | 用户期望的是“海图上下文”还是具有物理含义的 synthetic radar echo | DP-01/DP-03 | 高 | 未闭环 |
| BL-02 | 当前执行场景的 RadarParams.max_range 是否应替代 UI 2000 m 常量 | DP-05 | 高 | 未闭环 |
| BL-03 | 240 px 下默认保留哪些 ENC 类别才不遮挡目标 | DP-11/DP-14 | 中 | 未闭环 |
| BL-04 | 是否需要真实扫描时序、遮挡、clutter 和 detection probability | DP-03/DP-18/DP-19 | 高 | 未闭环 |
| BL-05 | Mini Map 目标应显示 measurement、track，还是允许 God tracker truth 并显式标源 | DP-04 | 高 | 未闭环 |

### 0.4 证据矩阵 [EV]

| ID | 来源类型 | 引用 | 检索置信 | 来源权威 | 场景适用 | 归属 |
|----|----------|------|----------|----------|----------|------|
| [R1] | DOMAIN_EVIDENCE | [R1] | 高 | 高 | 高 | DP-01/DP-03/DP-06/DP-07/DP-10 |
| [R2] | DOMAIN_EVIDENCE | [R2] | 高 | 高 | 高 | DP-02/DP-07/DP-11/DP-14 |
| [R3] | DOCUMENTED_INTENT | [R3] | 高 | 中 | 高 | DP-01/DP-08/DP-11 |
| [R4] | PROJECT_FACT | [R4] | 高 | 高 | 高 | DP-01/DP-05/DP-08/DP-09 |
| [R5] | PROJECT_FACT | [R5] | 高 | 高 | 高 | DP-03/DP-04/DP-18/DP-19 |
| [R6] | PROJECT_FACT | [R6] | 高 | 高 | 高 | DP-02/DP-06/DP-12/DP-15 |
| [R7] | PROJECT_FACT | [R7] | 高 | 高 | 高 | DP-04/DP-09/DP-21/DP-22 |

### 0.5 场景注册表 [SC]

| ID | 场景描述 | 约束/边界 | 驱动决策点 |
|----|----------|-----------|-----------|
| SC-01 | 本船前方 2 km 内存在岛屿和一艘动态目标 | 岛屿必须可见，但不可把 ENC 图形冒充实时回波 | DP-01/DP-02/DP-03 |
| SC-02 | ENC 可用、Radar measurements 不可用 | 必须显示 CHART CONTEXT / RADAR UNAVAILABLE，不冻结旧回波 | DP-07/DP-10/DP-15 |
| SC-03 | Radar measurements 可用、ENC tile 加载失败 | 目标/回波继续运行，chart layer 独立降级 | DP-07/DP-10/DP-15 |
| SC-04 | AIS 与 radar measurement 指向同一船 | 不重复画两个物理目标；来源可查 | DP-04/DP-21/DP-23 |
| SC-05 | 目标在探测圈外或量测陈旧 | 不显示为实时 radar target；不得以 truth 静默补位 | DP-04/DP-05/DP-22 |

### 0.6 裁决注册表 [VR]

| ID | 裁决对象 | 结论 | 采纳/弃用 | 理由 | 时间 |
|----|----------|------|-----------|------|------|

### 0.7 备选/弃用方案 [ALT]

| ID | 方案 | 弃用理由 | 对比于 |
|----|------|----------|--------|

### 0.8 技术规约注册表 [TS]

| ID | 类别 | 规约内容 | 单位/定义 | 来源 | 关联DP/接口 | 与现状差异 |
|----|------|----------|-----------|------|-------------|-----------|

---

## 参考文献

- [R1] IMO Resolution MSC.192(79), Revised Performance Standards for Radar Equipment, sections 5.24-5.33 and 9.4-9.6.
- [R2] IHO S-52 Edition 6.1.1, Specifications for Chart Content and Display Aspects of ECDIS, radar overlay and presentation priority guidance.
- [R3] OpenBridge, “OpenBridge 6.1 Video and Camera”, Figma Community Mini Map reference, 2026 snapshot.
- [R4] `web_gui/modules/radar-mini-map.js` and `web_gui/modules/situation-display.js` — current 2000 m Mini Map, target Risk boxes and 120° attention sector.
- [R5] `colav_simulator/core/sensing.py` — current Radar produces noisy point measurements for dynamic obstacles and optional clutter; no static land echo or radar video.
- [R6] `gui_server/main.py` — `/api/enc_info`, `/api/enc_tile`, and local-frame `enc_navigation_area.safe_water` are available; no SENC object subset is published to the browser.
- [R7] `web_gui/modules/telemetry-projection.js` — canonical sensor target projection distinguishes tracker and truth position sources.

---

## 演进日志(append-only · 时序 · 不可覆盖)

### Step1 · 行业调研·发现决策点  [2026-08-26 14:02]

- 模式判定: 重构。当前 RADAR Mini Map 已显示 2000 m 圈、目标三角、Risk 框和 120°扇区，但没有 chart context、static radar echo 或 radar-video provenance。
- 行业快调: IMO MSC.192(79)、IHO S-52、OpenBridge Mini Map 参考。
- 关键事实: IMO 允许 radar operational display 叠加 ENC，但要求同一 datum/scale/orientation/CCRP，Radar 优先且 chart 必须可辨识、可一键移除；position/chart 失效时不得保留误导叠加或冻结 radar picture。
- 项目快调: 可立即复用 ENC raster tile；safe-water polygon 是吃水相关安全海域，不等于 coastline；现有 Radar 只测动态目标点和 clutter，不能支持“岛屿雷达回波”真实性声明。
- 新增决策点: DP-01..DP-23。
- 技术分解: TD-01 ENC context renderer、TD-02 synthetic static radar echo、TD-03 dynamic radar target pipeline。
- 等待 Step1 内部确认门: 用户确认决策点覆盖后才进入 Step2。
