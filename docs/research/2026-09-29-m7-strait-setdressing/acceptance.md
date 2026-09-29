# M7 海峡布景与大气 — 验收证据

## M7-A 布景四要素（commit 4dee8b3c）

### 交付事实（确定性证据）

- **A1 岸桥+堆场**：16 台 STS 门架岸桥（8+8）+ 1916 箱堆（6 色板、4 block×12 列×3-5 层），
  Pasir Panjang（near_r1c0，quay -2380,-1000→-2290,-2350）+ Tuas 西泊位（far_r2c0，-20300,-2950→-18200,-3250），
  沿 S2 2026-03 码头岸线（site 分析 tmp/m7a/，pyproj 钉值）。
- **A2 锚地真实区**：东 OPL（≈1.21N 103.90E，6 槽）+ 西南（≈1.17N 103.71E，6 槽）；离线 RAW 采样
  全槽 < -23.7m（含 300m 大船 ±175m 角点盒，门限 < -5m）。
- **A3 填海岸线**：DEM/S2 交叉核查证实 S2-2026 码头平台在 GLO-30/GEBCO 期次缺失或 0 平台 →
  小块平整至 +2m（PP 241×326 texel、Tuas 104×29；不碰 tile 管线，BuildAll 重放幂等）。
- **A4 绿脊**：16 活跃远带 tile splat（滩涂 0-4m 橄榄 (0.36,0.40,0.22) / 丛林 >4m 深绿 (0.05,0.20,0.07)，
  base/mud/jungle 权重归一化，测试全域扫掠）+ 2214 基本体树卡（Terrain 树实例化，≤4000 上限，
  ≤220/tile，排除区生效）。**树卡来源链**：Kenney Nature Kit 无 3D 树 → Quaternius itch 直链被阻 →
  按任务链回退基本体卡（资产预算 2.9MB / 60MB）。
- **门禁**：EditMode 基线 265 → **279/279**（+14：UTM 对 pyproj 8 点钉值——首跑抓出 Snyder 级数漏乘
  cosφ 的 33m 偏差并修复、往返亚米、掩膜/权重、合成高度图锚地水深门、bounds、预算、确定性散布）；
  构建期实测门禁全过（m7a-build.log EXIT=0）：水深门 13 泊位/槽位最浅 -15.0m、航线 57 采样最浅 -46.9m；
  陆上门 16 岸桥基座+1916 箱堆角+2 平台角 ≥ +2.0m（fail-fast）。
- M6+M1 场景重建 exit=0/0；播放器 fresh 构建。

### 主 agent 实机验收（CUA，2026-09-29）

- 基线观感保持：海面明亮蓝绿、默认雾 8000m、随船视角白船体入画；C 四机位（追尾/船艏/桥楼/俯视）正常；
  G 自航启动顺滑。
- **fps 干净协议**（独立会话+零交互+预热后读稳态）：`overlays fps (10s avg)` 连续 4 条 **60.0**
  （frame_ms_avg=16.67 vsync 满帧间隔非饱和；gate ≥30 大余量过）；water queries/frame=0 (failed 0)。
  注：M6 记录 119.8 为当时刷新率/垂直同步状态，本轮 16.67ms=60Hz vsync 上限，非内容成本回归。
- 截图（本目录，内容 JPEG）：m7a-bow-early（艏向：左地平线远岸条带）、m7a-bridge（桥楼）、
  m7a-topdown-spawn（正俯视）、m7a-cam1-chase / m7a-topdown-cruise / m7a-topdown-cruise2（G 自航中）、
  m7a-bow-cruise（艏向航行）。
- 落位坐标核实（读 M7BackdropMath.cs:241-269 与 M6StraitSceneBootstrapper.cs:43）：hero 泊位
  (-1500,-5000) 艏向 134°；PP 码头距出生点 ≈3.4km（NW，雾内）；Tuas ≈19km（雾外）；东锚地 ≈11km（ESE）。

### Findings（转入 M7 review/修复批）

- **F1 岸桥天际线全程不可见（demo 构图）**：四机位均沿艏向（134° SE），PP 在艉后 3.4km、Tuas 雾外、
  航线 SE 向不经过两码头可视带 → "一眼辨识"对岸桥不成立。提案：C 循环加第五机位"瞭望"
  （船相对高角回望 ≈314°）——出生点即见 PP 岸桥+堆场+填海平台天际线；航线后段回望还能看到东锚地船群。
- **F2 绿脊雾缘可读性弱**：8000m 雾下远带只读出滩涂缘色带（颜色物理正确：Batam 低地 0-4m 滩涂带宽，
  丛林在内陆高地被雾衰减）。同一瞭望机位+M8 a4000 高空出片展示；Mac 档如实接受视距物理。
- **F3 树卡为基本体兜底**（来源链见上）：M8 高档可升级自绘 alpha 卡或 Fab Megaplants（届时用户在受控
  浏览器登录一次）。
- 非缺陷记录：俯视机位=船心近景（M6 语义），不做布局视图；锚地船群入视距需自航 ~35min（5m/s 航速真实感，
  不为演示加速）。

## M7-B（占位，待 B 批完成后补）


## M7-B 动目标与大气（commit e4c53261）

### 交付事实（确定性证据）

- **B1 浮标**：13 座 IALA-A（主航道带 10=3 红罐/3 绿锥/北南方位标 + 锚地进口 3 含安全水域标），
  BuoyBeacon 夜灯复用 NavigationLights 光弧工艺（快闪 1s/群闪 10s×3/长闪 8s×1，曲线有测试）。
- **B2 动目标**：渡轮（Medium 代役，编目无渡轮件）巴淡北部 (1.2005N 104.019E) ↔ 新加坡西南
  (1.25N 103.79E) 往返；拖轮（RAstar 3200）东锚地以南 2km 闭环；WaypointFollower autoStart，
  100m 步长逐点水深门 <0 fail-fast（含改道回归锚：合成岛压 x[3000,7000] z[-7600,-3400] 仍过）。
- **B3 大气三档**：HazyClear 默认 8000m/云 0.35/0EV/雨关；Cumulonimbus 4000m/云 0.80/−0.8EV/太阳×0.55；
  Thunderstorm 1500m/云 0.95/−1.6EV/太阳×0.30/雨 9000/s 粒子。smoothstep 3s 过渡（AdvanceAtmosphereTransition
  可测缝）；杠杆选型=Exposure.compensation .Override（自动曝光下压太阳会被直方图抵消，补偿 EV 才留得住）。
  WeatherGUI 下拉 + V 键循环。
- **B4 渔排**：5 组（木板+浮筒+棚）far_r3c4 活跃 tile Batam 北浅水带 [-8,-2]m 窗，FishFarmSway 系留微摇摆。
- **门禁**：EditMode 279→**297/297**（+18）；M6+M1 场景重建 exit=0/0；播放器 fresh。

### 主 agent 实机验收（CUA，2026-09-29）

- **三档大气切换全过**：V 键循环三次实拍（m7b-tier1-hazyclear / tier2-cumulonimbus / tier3-thunderstorm）——
  积雨云档云量 0.80/雾 4000/画面变暗可辨；雷暴档雨幕粒子+1500m 浓雾+天光压暗，三档一眼差异成立；
  面板下拉与滑条镜像同步（Cloud cover 0.35→0.80→0.95，Fog 8000→4000→1500）。
- **夜航**：T×2 至 h=0 实拍（m7b-night / night-bridge）——月夜海面、三船号灯 ON（census：Ferry/Houbei/Tug
  lights ON at h=0.0）、本船两舷灯光斑可见。
- **fps 干净协议**：60.0×4 连读（vsync 上限，gate ≥30 大余量过）。
- **probe 30/30**：`--sango-publisher` 启动 + `tools/sango_zmq_probe.py --count 30` → OK exit 0
  （20Hz 稳流 1600x900，M3 链路在 M7 全内容下完好）。

### 待裁决疑点与移交 review 批

- **L1 舷灯侧别（不下结论，测试钉死）**：夜拍两次读色均似"红在右舷"（艉后视角），但代码链三重自洽——
  ①DeriveAnchors 弓形框架 Port=−X 红；②ToNative(180°)+根旋转组合代数复核 world port 偏移·starboard<0
  （h=0/134° 双点验算）；③census 三船 rig 内部一致且 M2-D 对该约定做过视觉验收。census loa=937.8 为
  **网格原生单位口径**（×根缩放 0.0448=42m 实际，port ±151units=±6.8m 实际舷边），非悬空 bug。
  → review 批派组合级测试：fresh placement 后断言 port 灯世界坐标在 −starboard 半平面，一锤定音；
  另建议 census 日志标注单位口径。
- **F1 瞭望机位**（M7-A finding，本次修复项）：C 循环加第五机位（船相对高角回望 ≈314°）——出生点见
  PP 岸桥天际线，航线后段回望见东锚地船群；渡轮北端距出生点仅 ~2.6km（1.25N 103.79E），回望机位同时
  解决动目标可见性。
- **动目标/渔排/浮标日间视觉**：本批从出生点视距内不可达（雾 8000m 外），且无回望机位——census+水深门
  +测试为确定性证据，视觉复核随 F1 机位修复后补拍。
