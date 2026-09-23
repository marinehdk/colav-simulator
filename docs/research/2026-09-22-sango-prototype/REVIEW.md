# 阶段1方案独立评审（REVIEW）

- 日期：2026-09-22 ｜ 评审人：独立评审员（未参与调研与撰写）
- 评审对象：[PHASE1-PLAN.md](PHASE1-PLAN.md)，对照本目录 01–05 调研文档与仓库源码
- 评审方式：通读方案后，对方案引用的关键事实**逐条重跑核实**（未采信撰写者的标注），再按五轴找失败点
- 结论：**第 1 轮：1 high / 3 medium / 4 low，不通过；第 2 轮（修订版复核）：8 条全部解决、无新问题，通过**（见文末第 2 轮评审）

---

## 0. 本次评审实际执行的核实（证据清单）

| # | 核实项 | 命令/出处 | 结果 |
|---|---|---|---|
| V1 | FastAPI app 位置 | `sed -n '1650,1680p' gui_server/main.py` | `app = FastAPI(...)` 确在 :1658 ✅ |
| V2 | WebSocket 路由 | `sed -n '2130,2160p' gui_server/main.py` | `/ws/sessions/{session_id}` 确在 :2141，`transport=compact-v1/static-once-v1/shared-planner-v1` ✅ |
| V3 | 控制面 REST | `grep -n '@app.post\|@app.get' gui_server/main.py` | `POST /api/sessions`:1818、`/start`:1845、`/speed`:1863、`/step`:1871 ✅ |
| V4 | 遥测 schema | `sed -n '1140,1160p'`+`'1475,1560p'` | 信封 `schema_version:"1.0"`（:1150,:1480），含 `truth[]/plans/seq/sim_time/playback` ✅ |
| V5 | **compact-v1 是子集** | `sed -n '148,235p' gui_server/main.py` | compact 版剥掉每船 `measurements/tracks/colav`、弹掉 `os/obstacles`，另加 `transport.schema_version="colav.telemetry.compact@1"`（:152-160）⚠️ 方案未提 |
| V6 | 后端无检测回传路由 | V3 全路由清单 + :2141/:2153 两个 WS | 全部为遥测下行+控制上行，**无任何检测/观测中继端点** ✅（印证 04 文档 B.2） |
| V7 | Mac 硬件 | `system_profiler`/`df -h`/`ls /Applications/Unity/Hub/Editor` | M3 / 8GB / 数据卷 25Gi 可用（95% 满）/ Hub 已装且 Editor 目录为空 ✅ |
| V8 | a4000 硬件 | `ssh a4000 'nvidia-smi --query-gpu=...; free -g; df -h /'` | 2×A4000 16GB，GPU0 占 5248MiB / GPU1 空闲；125G RAM；根卷 95% 满剩 91G ✅ |
| V9 | README 坐标约定 | `grep -n 'North-East' README.md` | 确在 :14，NE 米制 rad ✅ |
| V10 | **psi 语义** | `web_gui/modules/scene-geography.js:25-31`、`scene-3d.js:210-213` | 艏向向量 =（北 cosψ，东 sinψ），即**北偏东、顺时针为正**——这是 F1 判定依据 |
| V11 | HANDOFF 引用 | 实读 `/var/folders/.../sango-sim-handoff-20260922-TrSSXG/HANDOFF.md`（277 行），抽查 :8,:37-38,:44,:53,:106,:120,:124,:136,:207 | 9 处引用全部与原文相符 ✅ |
| V12 | repo venv 可跑 fixture 命令 | `.venv/bin/python -c "import websockets, cv2; ..."` | websockets 16.1.1 + cv2 均可导入 ✅ |
| V13 | Unity 6.3 LTS 存在 | WebSearch（unity.com releases 页） | 6000.3 LTS，支持期至 2027-12 ✅ |
| V14 | Water System CPU 水高查询 | WebSearch（docs.unity3d.com HDRP Water scripting 页） | 官方确认：需开启 **Script Interactions**，且明示有 GPU→CPU 回读性能代价 ⚠️（方案未提代价） |
| V15 | Unity Personal 门槛 | WebSearch（Unity 许可条款） | Personal $200K 门槛属实；"非游戏 >$1M 须 Industry"未能直接复核（定价页 404），方案已列为 M0 前置核实项，可接受 |

未复核项（如实声明）：agx 未重查（方案阶段1/2 不依赖它，03 文档结论与本方案一致，不影响判定）；Unity 6.3 HDRP 在本机 8GB 的实际 fps/内存（无 Editor 可跑，方案自身以 M0 冒烟为闸门）；HDRP Water 对局部点光的反射表现（无 Unity 环境，见 F3）。

---

## 1. 视觉对齐

四张画面里，画面1（俯视 COLREG）、画面2（设置面板）、画面4（桥楼视角）的要素全部由"脚本绘制 + HDRP 原生能力"构成——LineRenderer 轨迹、时间球、UGUI 面板、世界空间箭头、Perlin 岛重建、Beaufort→波段参数映射——没有一项依赖未证实的能力，路线成立。**最可能做不出来的是画面3（夜间船艏视角），且方案对此没有回退路径**：其六个画面要素中两个有缺口——①"月/星光"：HDRP Physical Sky 是太阳驱动的解析天空，太阳落到地平线下只提供"变暗"，**不产生月盘和星空**，方案却把它列为验收要素并在 §3 选型 5 声称昼夜切换"零额外成本"；②"水面灯光拉长反射光路"：HDRP Water 对局部点光（舷灯/桅灯是 Point Light）的镜面反射表现未经验证，官方文档只确认了 CPU 水高查询与波段参数，而 §7 R2 只兜"海面整体观感（白帽/SSS）"不兜这个具体要素。两个缺口都有廉价解法（月光方向光+星穹 dome；不达标改加色拉伸面片假反射），但都必须先补进方案，否则 M2 验收打勾表在这两项上无依据可打。整体帧率风险（8GB M3）方案已用 M0 冒烟闸门如实覆盖，判定诚实。

## 2. YOLO 可接入

阶段1 主线（真值框投影，零推理）无懈可击：框本引擎已知，`DetectionOverlay` 只认"帧+框列表"，格式、延迟、部署位置三问在阶段1 语境下都消解了。遥测缝具体到接口：端点（V1–V3）、字段（V4）、时钟（`_simulation_loop` `interval=dt/multiplier`，main.py:1578-1626 本次核实）、坐标（V9）四件套齐全，fixture 命令依赖的 websockets 已在 venv 中（V12）。**缺口在检测框的"回传方向"**：方案 §2.2-3 称阶段2"换 a4000 YOLO 输出，组件零改动"，但本次核实后端全部路由均为遥测下行+控制上行（V6），不存在把 YOLO 框送回 Unity 或送进 tracker 的任何通道；`FramePublisher` 是单向出帧。也就是说缝钉住了"帧怎么出去"，没钉住"框怎么回来"——阶段2 真要换检测源时，消息 schema、时间戳对齐、通道（ZMQ 第二 socket 还是阶段3 observations 端点）全是空白。另外 compact-v1 是子集传输（V5），契约类若按全量 1.0 文档声明必填字段，接真流时会反序列化失败——细节见 F4/F5。

## 3. 硬件可行

对照 03-hardware.md 逐步骤重跑（V7/V8）：Mac 与 a4000 的每一项硬件事实全部吻合，方案没有任何一步"假设了不存在的能力"——恰恰相反，它把所有未实测项（8GB 跑 HDRP、串流、aarch64 Editor）都明确标注并以 M0 闸门兜住。两条 low 级软肋：① R1 回退③"a4000 Linux Editor + 串流"没提协调成本——a4000 上已有他人远程图形会话（HANDOFF.md:124，本次实读核实）与他人 GPU 进程（V8），在那台共享机上起交互式 GUI 会话不是单方可决定事项，时间盒 1 天的估算不含等待协调的时间；② 浮力方案依赖的 Water CPU 查询需开 Script Interactions，官方文档明示引入 GPU→CPU 回读代价（V14），在 8GB 统一内存、本来就贴着 R1 红线的机器上，这笔账没进 M0 冒烟清单——冒烟时若不开它，实测 fps 会比真实运行态偏乐观。

## 4. 工程量与最小性

10–17 人日与 01 文档 10–16 人日自洽；逐项扫过没有阶段3 的过度设计——不写 COLREG 裁决、不接推理、不做锁步、不建 KVM 基建，"三颗钉子"是缝的全部而非抽象框架，FramePublisher+probe 脚本（约 1 人日）是对"留缝"目标的合理兑现而非越界。里程碑验收大多命令/产物明确可查：M0 有 fps 闸门与内存记录，M2 有 `open sango/Builds/sango.app` 与四段录屏，M3 有可执行的 probe 命令和 fixture 测试（V12 已验证依赖存在）。两处可收紧：① §2.2-4 "第一天起做浮点原点偏移"——阶段1 场景（遭遇测试、50m 比例尺量级）远够不着浮点抖动阈值，机制属阶段2 千米级场景的需求，day-one 只需冻结"坐标系约定+原点取法"，偏移机制本身是提前量；② M1 验收"波高/白帽可感知增强"是纯主观判据，Beaufort 滑条→波段参数的映射数值没有锚点，验收时无表可对（JS-PM 档位是近似这点方案已诚实声明，不重复计入）。

## 5. 对比诚实性

决策表**公平，无 strawman**。本次实读了 HANDOFF.md 原件（277 行）并抽查方案引用的 9 处行号——P0 直通必经（:8"Windows 尚未安装完成…GPU1 尚未释放或直通"）、1A/1B 路线（:37-38）、三条责任原则（:53）、IOMMU 组（:120）、他人图形会话（:124）、127.0.0.1-only VNC（:136）、无产品密钥（:207）——全部与原文相符，"放弃默认地位/降为可选"的处置有事实支撑而非树靶子。"（隐含）复刻 Barracuda+YOLOX 为阶段1 必选"一行的措辞也经得起核对：旧方案 1B 原文是"真实YOLOX推理…首轮是否纳入完整验收仍待用户确认"，方案以"隐含/必选"概括略有强化，但替换理由（阶段1 目标是画面、两钉子保升级路径）是实质性论证，不构成不公平比较。保留项（视觉基准卡、ZIP 备用、责任原则、run-guide）与放弃项理由对称，溯源完整。

---

## Findings 一览

| # | 轴 | 位置 | 问题 | 修复建议 | 严重度 |
|---|---|---|---|---|---|
| F1 | 2/1 | PHASE1-PLAN §2.2-4、§8.5（源自 04 文档 B.3） | **heading 映射符号错误**：`psi→绕 y 旋转 -psi` 应为 `+psi`。证据链：后端艏向向量=（北 cosψ，东 sinψ）（`web_gui/modules/scene-geography.js:25-31`、`scene-3d.js:213` 船眼置于 `x-cosψ, y-sinψ` 舉后），即北偏东顺时针为正；Unity `Euler(0,θ,0)` 使 +Z（北）转向 +X（东）需 θ=+90°，故 Unity `rotation.y = +ψ` 才指向东偏。按 −ψ 实现，非正北/正东航向全部镜像，画面1/4 立即出错，且该错误会被照抄进阶段2 桥接代码 | §2.2-4 与 §8.5 改为 `rotation.y = +psi·Rad2Deg`（东=x、北=z 前提下），并在阶段2 首日用 psi=90°（朝东）场景做视觉回归；04 文档 B.3 同步勘误 | **high** |
| F2 | 1 | §1.3 画面3、§3 选型表 5 | "月/星光"列为画面3 验收要素，但 Physical Sky 是太阳驱动解析天空，无月盘/星空输出；"昼夜切换零额外成本"只覆盖变暗，该要素按方案手段做不出来 | M1/M2 增补"月光方向光 + 星穹（HDRI 或程序化星点球壳）"约 0.5–1 人日；或将画面3 要素降级为"暗夜空"并同步改验收条款 | medium |
| F3 | 1 | §1.3 画面3、§7 R2 | "水面灯光拉长反射光路"未验证：HDRP Water 对局部点光的镜面响应无官方确认（官方仅确认 CPU 水高查询与波段参数），R2 只兜海面整体观感，此要素失败时无回退 | M2 首日 0.5 人日专项验证点光反射；不达标用加色拉伸面片/粒子假反射兜底，写入 R2 对策 | medium |
| F4 | 2 | §2.1 L3、§3 表14、§5 M3 | 阶段2 检测框回传通道无契约：后端不存在任何检测/观测中继路由（本次核实全路由清单），FramePublisher 单向出帧；"DetectionOverlay 组件零改动"成立，但"换 a4000 YOLO 输出"的框从哪条路、什么格式回来完全未定义——缝只钉了一半 | M3 增补第四颗钉子：冻结 `DetectionResult` 消息 schema（box/类别/置信度/帧时间戳）+ 通道选型（Unity 侧 ZMQ SUB，或阶段3 `POST /api/sessions/{id}/observations` 建议稿），允许默认不激活 | medium |
| F5 | 2 | §5 M3-3、§8.3 | compact-v1 是子集传输：信封仍为 `schema_version:"1.0"` 但每船剥掉 `measurements/tracks/colav`、弹掉 `os/obstacles`，另加 `transport.schema_version:"colav.telemetry.compact@1"`（`gui_server/main.py:150-160`，本次核实）。契约类若按全量 1.0 文档声明必填字段，接真流即反序列化失败 | `ColavTelemetry` 明确按 compact-v1 子集声明必填字段；EditMode 测试断言 `transport.schema_version` 且被剥字段可缺省 | low |
| F6 | 3 | §4、§7 R1③ | a4000 串流回退漏算共享机协调：该机已有他人远程图形会话（HANDOFF.md:124）与他人 GPU 进程（V8 复核），起交互式 GUI 会话需协调，1 天时间盒不含等待 | R1③ 前置"与管理员协调窗口"条件；优先评估 `-batchmode` 离屏出片等非交互路径 | low |
| F7 | 3 | §5 M0、§7 R1 | 浮力查询成本未入冒烟清单：Water CPU 查询需开 Script Interactions，官方文档明示 GPU→CPU 回读代价（V14）；不开它测出的 M0 fps 偏乐观，开了才见真实负担 | M0 冒烟即开启 Script Interactions 并带 6 船低模逐三角形查询一起实测 fps/内存 | low |
| F8 | 4 | §1.3、§5 M1 | M1 验收"波高/白帽可感知增强"无量化锚点，Beaufort→Water band 参数映射无数值表，验收时无表可对 | 给出 Beaufort→风速 m/s→波段参数（风带幅值/涟漪风速）映射表，配固定机位/固定参数截图对作为证据 | low |

---

## 评审结论

方案的调查密度和诚实度高于常态：未验证项全部显式声明、硬边界清晰、验收大多落到命令/产物。但存在 1 个 high（F1 heading 符号错误——事实错误，且会污染阶段2 契约代码）与 3 个 medium（画面3 两要素无实现路径/无回退、检测框回传缝只钉一半）。按"无 high 方可通过"的约定，**本次不通过**；修复 F1–F4 后无需重审全案，抽查修复合入即可。

---

# 第 2 轮评审（修订版复核，2026-09-22）

## 方法

重读修订版 PHASE1-PLAN.md 全文与第 1 轮 REVIEW.md，逐条核对 8 项 findings；本次实际执行的核实：

1. `grep -n 'psi' docs/research/2026-09-22-sango-prototype/04-prior-art-colav-seam.md` → `:56` 已改为 `绕 y 旋转 **+psi` 并附日期勘误注（引用 scene-geography.js:25-31、scene-3d.js:213-214）——方案声称"04 文档已同步勘误"**属实**；
2. `grep -n 'Rad2Deg\|\-psi' PHASE1-PLAN.md` → 存留的 `-psi` 全部位于勘误说明文字内（:118、:252、:275），生效约定均为 `+psi·Rad2Deg`（§2.2-4、§8.5）；
3. `sed -n '148,170p' gui_server/main.py`（带行号输出）→ `:151`=`def _compact_stream_payload`、`:160`=`"schema_version": "colav.telemetry.compact@1"`、`:164`=剥除 measurements/tracks/colav 的推导——修订版改引的 `main.py:151,160,164` **准确**；
4. 复算修订版 M1 验收的蒲福锚点（公认风级换算）：B0<1kn≈0.5 m/s、B3 7–10kn（中值≈4.4）、B6 22–27kn（≈12.6）、B9 41–47kn（≈22.7）——方案写 B0≈0.5/B3≈4.5/B6≈12.5/B9≈22.5，**数值正确**。

## 逐条核对（8/8 已解决）

| # | 上轮问题 | 判定 | 修订证据（PHASE1-PLAN.md 行号为本轮实测） |
|---|---|---|---|
| F1 | −psi 符号错误（high） | ✅ 解决 | §2.2-4（:118）、§8.5（:252）均改 `rotation.y = +psi·Rad2Deg` 并注明勘误依据；§8.5 增阶段2 首日 psi=90°（朝东）艏向视觉回归验收动作；04 文档 B.3（:56）已同步勘误（本轮 grep 核实） |
| F2 | 月/星光无实现路径（medium） | ✅ 解决 | §1.3 画面3（:58）验收要素降为"暗夜空"，月/星改可选加分项；§3 表 5（:134）明写"Physical Sky 不产生月盘/星空"边界，删除"零额外成本"表述；§5 M1（:179）列为可选项不计基线工程量 |
| F3 | 水面灯光反射未验证、R2 不兜（medium） | ✅ 解决 | §1.3 画面3（:58-59）标注【待验证要素】且"真反射或兜底假反射均算达标"；§5 M2（:189）首日 0.5 人日专项验证；§7 R2 新增第④条兜底（加色拉伸面片/粒子），计入 M2 工程量 |
| F4 | 检测框回传通道无契约（medium） | ✅ 解决 | 四颗钉子（§0 :12、§2.1 :97、§3 表14④ :143）；§5 M3（:198）冻结 DetectionResult schema（frame_seq/frame_time/source/detections[]{box_xyxy,class_id,class_name,confidence}）为 `sango/Docs/contracts/detection-result-v1.md` + C# DTO；通道选型稿=默认 Unity ZMQ SUB ↔ a4000 YOLO（后端零改动）、备选 observations 端点；验收 4（:204）增 `DetectionResultRoundTrip` 回环测试；§8.8（:255）明确"框进 Colav tracker 属阶段3、需后端改动"，与"后端零改动"不再冲突 |
| F5 | compact-v1 子集语义（low） | ✅ 解决 | §5 M3（:198,203）与 §8.3（:250）按子集声明必填字段；验收 3 断言 `transport.schema_version=="colav.telemetry.compact@1"` + 被剥字段可缺省；行号 `main.py:151,160,164` 本轮 sed 核实准确 |
| F6 | a4000 协调漏算（low） | ✅ 解决 | §4 a4000 行（:156）注明他人远程图形会话先例（引 HANDOFF:124）；§7 R1③（:234）增"先与管理员协调窗口、等待不计入时间盒"前置条件，并优先 `-batchmode` 离屏出片、串流降其次 |
| F7 | 冒烟未含浮力查询成本（low） | ✅ 解决 | §5 M0（:169,173）明确"开启 Script Interactions + 6 艘低模船逐三角形水高查询"条件下实测，"仅测裸海面不算数"；R1①（:234）同步 |
| F8 | M1 无量化锚点（low） | ✅ 解决 | §5 M1（:180-183）交付 `sango/Docs/beaufort-water-mapping.md`，蒲福→风速→band 参数锚点（数值本轮复算正确，且标注"起调值，推断"），每级固定机位+固定参数截图对，录屏验收要求面板风速与表一致 |

## 新问题排查

逐节复读修订版新增文字，**未发现新的 high/medium/low 问题**。两点备注（不构成 findings）：

1. **M3 工作量下沿承压**：M3 内容由 5 项增至 8 项（新增 DetectionResult 契约+DTO+回环测试 ≈0.5 人日），修订记录称仍落 2–3 人日区间——区间上沿可覆盖，但执行时应优先做钉子③④，视觉基准卡核对可顺延，避免里程碑尾部积压。
2. §6 表头仍写"HANDOFF.md…276 行"（实测 `wc -l` = 277）——沿自 05 文档的描述性计数偏差，无实质影响。

## 第 2 轮结论

**通过（approved，0 high / 0 medium / 0 low）。** 全部 8 项 findings 已按建议方向修复且证据可查（两处源码行号、一处跨文档勘误、一组数值锚点均经本轮命令核实）；修订未引入新问题。可按 M0 开工。
