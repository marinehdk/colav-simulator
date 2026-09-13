# 原版 GNC 集成：全量变更记录（colleague handover master record）

日期：2026-09-13。性质：**一次性交接文档**——自 2026-09-10 原版迁入以来我方全部修改的完整记录（我方代码变更 + 同事侧参考补丁），每条含动机、证据、变更内容与验证结果。同事采纳时按本档索引，无需多轮往返。

配套：[登记册 R1-R16](2026-09-11-colleague-structural-issues-register.md)（问题台账）· [同事参考包](../../colleague-proposal/README.md)（可应用 diff）· [诊断政策](2026-09-11-original-gnc-diagnostic-policy.md)（D1-D3 门槛）· 评估档 p2-p4 / d3 / 评分报告。

## 一、战役里程碑

| 日期 | 轮次 | 结果 |
|---|---|---|
| 09-10 | 迁入+嵌入 | 保真 70/70 工况、28/28 回放；产品 0/24（契约 seam 全拒） |
| 09-11 | P1 seam | 准入 0→24/24；addressable 拒因 13,287→13 |
| 09-12 | P2-P4+D3 | 硬安全全 PASS；D2 三判据过；D3 未过（goal/COLREG） |
| 09-12 | 不合理项轮 | COLREG 0 不合规；VO/Fan 修复 |
| 09-12晚 | p9 | VO/Fan 16/16+16/16 首次双全绿；Mid CS 对双环境稳定 |
| 09-13 | p10 | （本轮，goal 轴+Mid 收尾，见 §五） |

## 二、我方代码变更记录（按子系统）

### 2.1 准入 seam（bridge，2026-09-11）

| Commit | 内容 | 证据 |
|---|---|---|
| `2c3fd4c7`/`88fb3a3e`/`15ed27f0` | prefix-splice 路线构造：计划在 150 m avoidance 层内可接纳；mixed nav-mode tagging；reference 轮转时重建 splice | fan 461/461、vo 70/70 接纳 |
| `0cadde77`/`37d87c8d`/`5a9e95fc` | splice 交叉点反向门修剪 + manager 腿度量对齐 + 不可接纳 splice 扣发 | reverse 拒 58/111→0 |
| `110e0ecd` | R-B1/B2/B3：intent 数值容差（1-ULP 抖动消除）；splice 对 nominal 参考（非前次 splice）；降解速度不吸收进镜像；sub-floor prefix 清理；丢弃必带原因遥测；静态危害不触发 avoidance tag | fan-HO-E4 22代/50s→<10；vo-OT-E0 毒化前缀修复 |

### 2.2 VO planner

| Commit | 内容 | 证据 |
|---|---|---|
| `e751e5f3` | 速度窗包络 mask（[舵效,帽]+限速 course 弧 availability）+ τ_course horizon 206.8s + hysteresis | 激活延迟 32-112s→0；HO 双格 INF→通过 |
| `2862e6ff` | 窗口 scope 到活遭遇+网格行锚定 | — |
| `74b2a0bc` | cruise 带加密（0.1m/s 量子）+ 遭遇门闩锁修复（空规则集仍 truthy）+ give-way 家族策略 | vo-CS-E4 43m 差距达标类问题 |
| `c17ad1e1` | give-way 承诺期 port 候选置不可行（in-extremis 豁免）+家族池限 starboard 半圆+平局偏正 | R15 |
| `a998023d` | 未分类首拍 starboard 先验（分类滞后一拍漏洞） | p6b 伪影 |
| `e7a317a7` | stand-on hold 可执行化：held 单元被窗口排除时保持航向+最近可执行速度行（字节级不变） | vo-OT-E4 COMPLETED+PASS 1148.9m（R16） |
| `4a0208e2` | **TCPA 门控包络**：遭遇临界期（realized TCPA<120s 或 risk 激活）保守窗；宽松期（TCPA≥150s 或 CPA 已过 30s，双带滞回防抖）解锁巡航行 | goal 轴核心；p8b 无条件加宽教训（HO 净距 453→79m）已消化 |

### 2.3 Fan planner

| Commit | 内容 | 证据 |
|---|---|---|
| `1665bfe7` | rollout 用 reported 响应（τ=86.78s）+course 行 wrap（1-ULP 抖动消除，20 万样本验证） | fan 8/8 PASS；HO-E4 43.95→112.7m |
| `94c1ae58` | 静态约束标志绑定化（ENC 远距危害不再锁死意图） | fan-HO SOG 0.93→2.7-4.4 |
| `7e20ccdd` | `ownship_max_speed_mps` 入 PlannerInput+fan 请求钳到报告上限 | 帽诚实化 |

### 2.4 Mid planner / 生命周期

| Commit | 内容 | 证据 |
|---|---|---|
| `51eea350` | R8 预算：solver slice floor 1.0s（streak 降级不再饿死 IPOPT） | HO-E0 过 335s 墙 |
| `b45717e5`/`c3055592` | 速度界 staging 到 rate-reachable 走廊；CPA 窗起点诚实化+空窗回退 | OT 净距 −22→+113m |
| `7188ab6e` | `_mid_deviation` 短于 margin 时 hold 活跃航线（frozen-manager 忠实） | splice-margin 类消除 |
| `4a49b947` | 走廊 re-entry 夹紧对称化（starboard-only bug）+CPA 硬窗含 recovery knot+1 | MS-E0 优化器可行；OT +406.7m |
| `c8fa7414`/`d74e32a0` | 到达制动尾部（lag-based，落执行带） | CS-E4 13.5m 短板消除 |
| `70928754`/`f0971c67`/`39a0be8e` | 恢复横漂软屏障+seed 质量 gated 回落 | CS-E0 wander 843.8→551.6m |
| `8d26532a` | F1 重校：release 等待 envelope 与 corridor CPA 较晚者 | CS-E0/E4 环境轴翻转修复起点 |
| `9bed4873` | iterate filter 切 L4 证据结点+失败 NLP 全量持久化 | MS 数值证据武装 |
| `00c64a64` | HO 速度流失升级：give-way 承诺期 own<max(舵速,30%基线) 且接近→MUST_ACT | HO 死因从静默流失变为显式 |
| `c9d3cec5` | keep-way floor：SPEED_BLEED_KEEP_WAY 升级时 directive 速度下界=max(舵速,0.3×基线) | HO 命令速度不再 decay 至 0.93 |
| `2f247110` | MS 走廊接缝 ramp（rot_max×dt；12 rot-step 单结点跳变消除） | CS 对双环境稳定 COMPLETED |

### 2.5 资格/评分/工具

| Commit | 内容 | 证据 |
|---|---|---|
| `014c8a36`/`89ec13dd`/`055b0b5c` | **R2 更正**：v1 R²=0.344 系我方导数基度量错误；轨迹基 speed 0.9848/course 0.9898 一阶合格；capability tuple 诚实解锁（阈值 0.90 入码） | Mid TRACKABILITY 8/8 拒→0 |
| `a70c454b`/`e0f446d2`/`77404ce6` | Woerner 评分器 v1→v2：命令层改向检测+事件链归因+锚定目标重分类+port 航向否决移除+**基线改 pre-encounter heading**（route 参照会把初始对线记成 port 104-120° 伪影） | 4 假不合规翻案；COLREG 判定可信化 |
| `f44039c5` | R11 归因：4 例"不合规"全为评分伪影（0 真违规）+反事实工具 | 评分器修正依据 |
| `5ee43a4e`/`7ad674d0`/`d40d786f` 等 | campaign 工具：subset runner、resume 续跑、mid runner、NLP dumper、评分 CLI | 全部可复现 |

### 2.6 嵌入层（早期，0910-0911）

`3374b333`/`393ab87c`/`f837bab3`/`77967191`/`8b96a86e`（迁入 5 commits，见迁移报告）+ adapter 包络/身份注入（`936cd364` max_speed plumb、`09812d2b`→`157d73c7` proposal-aware 包络）。

## 三、同事侧参考补丁（P-C 系列，待采纳）

详见 [colleague-proposal/](../../colleague-proposal/README.md)。要点：

- **P-C1（R3）**：协议层发现——CT 折叠全部 avoidance 字串到 code 6、guidance 解码 6="emergency_avoidance"（帽键），guidance-only 补丁无效；方案=emergency 保 6、普通 avoidance 新 code 10（沿同事自身 `emergency_behavior()` 区分），CT guard/FAP 谓词 6+10 双收。
- **P-C2（R13）**：manager 角降级全局 min 平压→分段作用+通过顶点恢复+舵速 floor 2.5；探针 `[1.47×4]→[2.5,2.5,2.5,7.8]`。
- **P-C3（R14）**：decel 检查执行速度+剩余距离+模式 floor（cruise≥0.2 vs berthing 0.08）+revision 滞回；静止触发误报消除。
- 调参建议（未改默认）：`max_yaw_rate_deg_s` 1.2°/s ⇒ 7m/s 需 R=334m，中度弯即降级。
- **新发现待登记（p10 后补）**：guidance 内部速度调度层（rejoin/XTE 帽 3.0、转弯帽 4.2、FAIL_SAFE 进入）在命令巡航速时仍压执行 SOG 至 ~3.05-3.2——goal 轴剩余瓶颈，属 R13 家族扩展。

## 四、误报更正记录（透明度）

1. **R2 撤回**：v1 "speed 通道 R²=0.344 不合格"为我方导数基度量错误（轨迹基 0.9848 合格）；"首解超时"同为误诊（designed quality stop）。同事 speed 模型无缺陷。
2. **R11 翻案**：4 例 MS"port 改向不合规"全为评分伪影（锚定目标/psi 抖动/航线恢复斜坡）。
3. **p6b vo-CS"真违规"**：实为评分器初对线基线伪影（VO 实际 starboard 11.25°）。

## 五、闭环验证轮次（24 格，seed 0，COLREG v2）

| 轮 | 构建 | VO/Fan | Mid | goal | COLREG |
|---|---|---|---|---|---|
| 基线 0910 | 未打补丁 | 6/16+2 PASS | 0/8 | 3 | 4 NC |
| p6 | 未打补丁（全部我方修复） | 16/16+16 | 2/8（CS-E4） | 3 | 12/9/1/4 |
| p8 | P-C1+2+3 | 15/16+15 | — | 3 | — |
| p9 | P-C1+2+3 | **16/16+16** | 2/8（CS 对稳定） | 3 | **16/10/0/4** |
| p10 | P-C1+2+3+goal 轴 | 16/16+16 | 1/8（HO-E4；CS 崩溃→见 p10b） | **4**（fan 单船全 True） | 17/4/**0** |
| p10b | +hold 静态门 | （VO 不变） | 1/8 稳定，其余收敛至 L4 接受层 | — | — |

**p10/p10b 收敛态**：VO/Fan 全绿+goal 4（fan 单船全达标；VO 执行压制在 guidance 调度层=rejoin/XTE 帽 3.0/转弯帽 4.2/FAIL_SAFE，同事侧 R13 家族扩展，命令巡航 6.77 而执行 ~3.05）；Mid 打地鼠终止——根因链=keep-way floor 保速→后期几何变化→目标重捕获→STAND_ON 全 horizon 航向钉±5°→钉住航线撞海图岛（static 场 −902.6m 穿透）→`ce00b3ff` hold 静态清障门（Rule 17(a)(ii) 时序，已承诺 hold 字节级不变）；剩余失败单层收敛：CS/OT/MS=L4 候选诚实拒绝、HO-E0=corridor-release 协调 open。

## 六、采纳流程建议

1. 同事评审三份 diff（按 P-C1→P-C2→P-C3 顺序应用；`grep -v '^//'` 剥注解）。
2. 采纳后告知：我方将登记册对应条目转 `verified-fixed`，以贵方仓库版本重跑 24 格回归并出对照报告。
3. 需贵方答复：S3 warm-seed 不变量意图；`minimum_steerage_speed` yaml 键共享；code 10 若有其他消费节点需确认。
4. 我方剩余 open（不依赖贵方）：Mid HO planner 联动验证、OT/MS L4 接受层、MS-E0 冷种子、guidance 调度层瓶颈（P-C1 采纳后量化）。
