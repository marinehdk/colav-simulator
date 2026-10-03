# P3-S6 双轴自审（spec #90 收口段，2026-10-02）

范围：S6 diff = D3 序列化对称修复 + D1/D2 默认翻转 + capabilities 产品面（vimmjipda 白名单/
默认/实验元组镜像/G2 档）+ head_on radar_x 装配 + 探针（obs 默认会话化、新 E2E 探针）+
钉值测试跟随 + 文档。方法：Spec 轴逐条对照 #90 与 00-PLAN §0；Standards 轴对照仓库
白名单/契约纪律。P1/P2 就地修，P3 记录。

## Spec 轴

### #90 末段（S6）交付项

| 项 | 状态 | 证据 |
|---|---|---|
| 默认 tracker 翻转（Config 项，S6 末全量回归后翻） | ✅ | D1 `trackers.py Config.god_tracker=False`；D2 `SessionCreateRequest.tracker_id="vimmjipda"` + prewarm + `policy.default_tracker_id`；顺序 = 修 D3 → 单测 → 翻 D1 → 全量 → 翻 D2（审计 §3 执行面照做） |
| E2E：全传感器会话 | ✅ | `tools/sango_phase3_e2e_probe.mjs` 双会话实证（见下 B 节）；`output/sango-phase3-e2e/` |
| 双轴 review | ✅ | 本文档 |

### 00-PLAN §0 完成定义六条（E2E 验收单）逐条

1. **量测→融合→确认航迹 + 存在概率/置信度数据产品**：WS `truth[].tracks` §6 三平行数组
   断言 + `GET confirmed-tracks` 冻结信封非空（E2E B4）；数据产品 schema 于 S5 冻结。
   附带发现（P2 已记录，见 Standards-3）：外部 vimmjipda 接口只消费 legacy Radar 通道，
   radar_x 相机雷达三源融合的"雷达侧"当前由 legacy Radar 承担；radar_x 进 vimmjipda
   需外部仓库工作（下阶段立项）。
2. **X 波段雷达 + PPI 面板**：head_on 场景装配 `radar_x`（RadarXParams 契约锚点默认值，
   schema 过闸实测）；god 链实测量测缓存含 finite radar_x 组；PPI 面板实开实绘截图。
3. **桅杆机位族 + IR + LiDAR + sensor_mode**：E2E B 段 eo→ir→lidar→eo 全回路（灰度
   spread≤12 黑白证 / dark 0.97 vs 0.12 + lit 点云证 / EO spread 回复），Player.log 双证。
4. **AIS 目标层**：符号层渲染 + 目标卡（source=AIS、state、assoc 全非占位）截图。
5. **IPDA 存在概率贯通**：vimmjipda 会话 WS existence 采样 + confirmed-tracks 端点；
   god 钉 1.0 与 vimmjipda 动态值路径分离断言（`dynamic || confirmedOk`，任务口径的
   "短窗全 confirmed 则端点非空+字段在场"回退内建）。
6. **YOLO 检测框进 tracker**：observations 端点 accepted_frames>0 且 sensor_id=2
   detections>0（obs 探针在翻转后默认 vimmjipda 会话上复跑 PASS = 量测缓存消费链照常）。
7. **传感器视角切换**：同 3；twin-bridge-v1 只加字段未破契约。

### 硬边界遵守（00-PLAN §3 + 任务硬边界）

- **白名单外零改动**：diff 触点 = observations/sensing/trackers/capabilities/gui_server/web
  tracker 选项（D2 联动，任务明示允许）+ 场景装配（任务明示允许）+ 探针/测试/文档。
  compact-v1/twin-bridge-v1 契约零字节改动（`git diff --stat` 可证：无 `sango/Docs/contracts/`
  与 Unity 文件）。Unity 零改动（EditMode 免跑）。
- **外部仓库零改动**：`/Users/marine/Code/ecosystem/vimmjipda` 未触碰；vimmjipda 的
  Radar-only 约束以适配层文档 + E2E 双会话设计消化，未在适配层做传感器注入魔术。
- **修既有测试只改声明**：唯一语义性新红 `test_historical_replay`（generation 重置语义属
  GodTracker 生命周期通道）按 `trackers=[(0, GodTracker())]` 显式声明修复（与 kuwata 工艺
  一致），断言未动。其余为产品策略钉值跟随（见 Standards-2）。
- **god 保留为诊断通道**：policy `tracker_ids=("god","vimmjipda")` 并列；显式 god 会话
  实测可建（回退路径 1）；场景显式 `god_tracker: ''` 回环保真（D3 单测三态）。

## Standards 轴

1. **白名单外零改动自查**：`git status` 逐文件核对——`colav_simulator/core/tracking/trackers.py`
   （D1/D3，白名单）、`colav_simulator/experiment/capabilities.py`（产品策略面，翻转的
   定义域）、`gui_server/main.py`（D2 两处 + 注释）、`web_gui/modules/config-shell.js`
   （TRACKER_LABELS 一项，D2 联动）、`scenarios/head_on.yaml`（雷达装配，写档于 yaml 注释）、
   `tools/sango_twin_obs_probe.mjs`（默认会话化，任务 A5）、`tools/sango_phase3_e2e_probe.mjs`
   （新增）、测试 5 文件钉值跟随 + 1 新测试文件、文档 3 文件。无契约/Unity/外部仓库改动。

2. **契约只加字段自查**：REST/WS 既有路由零删除零改形；新面 = capabilities 元组表镜像
   （EXPERIMENTAL，诚实标注 `experimental_fusion_tracker_default`/G1 语义，不克隆 god 实测
   数字进 VERIFIED）+ `minimum_grade` 集合加 vimmjipda + TRACKERS["vimmjipda"] G1→G2
   （升档理由写入注释：S5 离线对拍 + 阶段3 live E2E 链 = runtime_and_interface_load；
   正式 RMSE/NIS/NEES/ID-switch 门仍开，known_failure 保留如实声明）。钉值测试跟随 =
   策略即 spec 的机械更新（policy 字典/selectable 集合/CLI+batch 默认/catalog defaults），
   逐处留 `P3-S6 flip` 注释可溯源。

3. **P1/P2 就地修，P3 记录**：
   - P1（修）：D3 序列化不对称（翻转前置）；`test_historical_replay` 翻转新红（显式 god
     声明）；`test_historical_session_create` D2 元组镜像钉值跟随；E2E 探针三处设计缺陷
     （WS 采样器过早启动、AIS 卡片选择器不实、head_on.yaml 连带行尾归一化已还原）——
     开发中自纠。
   - P2（就地修 + 记录）：vimmjipda Radar-only 通道约束 → E2E 双会话设计（god 会话承载
     radar_x/PPI/显示腿），并在 E2E README/00-PLAN 完成记录披露——**radar_x 进 vimmjipda
     融合 = 下阶段外部仓库立项**；vimmjipda 会话前 ~2 分钟无航迹（目标 2.8km > legacy
     radar 2000m 量程）→ 探针 WS 采样器改为"等航迹出现"门。
   - P3（记录不追）：环境退化批 36 例 + test_colreg_scoring 全量段错误 →
     [preexisting-failures.md](preexisting-failures.md)（裸 HEAD stash 对照证实与 S6 无关）。

4. **预存失败台账**：见 [preexisting-failures.md](preexisting-failures.md)。S6 终轮全量
   口径 = 预存红集合与 S6 前基线逐条对齐（零新增），数字见 00-PLAN 完成记录。

5. **可复现性**：所有验收命令（全量 pytest / web / 探针 / 会话回退）均写入
   00-PLAN 完成记录与 E2E README，主 Agent 可独立复跑。

## 裁决

**APPROVE**（自审档；主 Agent 独立验收为准）。翻转三处 + 序列化修复按审计顺序执行且
每步全量验证；六条完成定义全部有探针级实证；边界纪律无违例。遗留（不阻塞关票）：
radar_x→vimmjipda 融合（外部仓库）、环境退化批 triage、colreg_scoring 段错误立项。
