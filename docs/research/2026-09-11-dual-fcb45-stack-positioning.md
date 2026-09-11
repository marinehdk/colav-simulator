# 双 FCB45 栈定位 ADR（dual FCB45 stack positioning）

日期：2026-09-11。状态：Accepted。范围：本项目内两套 4DOF FCB45 全栈的共存、分工与演化。关联：[诊断运行政策](2026-09-11-original-gnc-diagnostic-policy.md)、[同事侧结构性问题登记册](2026-09-11-colleague-structural-issues-register.md)。

## 背景

同事 4DOF FCB45 全栈（ILOS + PID/SMC + QP/PGD 三推进器两舵两艏推）在本仓库以两种形态同时存在：

1. 原版 C++ 后端（original backend）：`cpp/original_gnc` 构建产物 + `colav_simulator/original_gnc` Python 嵌入层，独立服务面 8014，构建产物由 `COLAV_ORIGINAL_GNC_BUILD` / `COLAV_ORIGINAL_GNC_SOURCE` 指定（[cpp/original_gnc/README.md](../../cpp/original_gnc/README.md)）；冻结源 `L4-5_source_only_20260824_v2`，库身份走 `verify_build` 链（[native.py](../../colav_simulator/original_gnc/native.py)）。
2. Python 工程栈（engineering stack）：`colav_simulator/modular_gnc` presets（`legacy` / `ideal` / `without_guidance` / `full`），默认服务面 8010。

两栈同源于同事设计，但实现、构建与资格完全不同。混用两者的结论，会让"同事栈到底行不行"永远测不清楚——这是设立本 ADR 的直接动机。

## 决策

**原版 C++ 后端 = fidelity reference + product integration target。**"同事栈是否支持我们的避碰"这一类问题，只允许用原版后端回答。规则：

- 从不静默 fallback：缺快照、资产或有效库时后端不可用，不退回旧 Full 后端（集成 24 格均 `fallback_used=false` 是既成约束，不是可选项）。
- `verify_build` 身份链强制：build manifest、extraction 台账、动态库 SHA256 齐全且一致，运行才算数；无身份的原版运行不进入任何证据链。

**Python 工程栈 = fast iteration + regression baseline + 当前产品演示。**它不是保真对象，不是同事栈替身；其结论不得迁移到原版后端（口径表见[诊断政策](2026-09-11-original-gnc-diagnostic-policy.md)）。

**比较规则：**同一 planner × 同一场景 × 两个后端成对运行；行为差异（接受/拒绝、轨迹、时序）逐条登记进[结构性问题登记册](2026-09-11-colleague-structural-issues-register.md)，附双方 trace。这份成对证据就是对同事沟通的证据底座——报问题凭 trace，不凭印象。

**长期演化：**原版后端按诊断政策 D1→D2→D3 阶梯逐级毕业；python 栈作为 regression oracle 永久保留——不删除、不降级、不合并。

**命名：**catalog preset id 永远显式区分后端。python 侧沿用 modular_gnc preset id；原版侧统一 `original_gnc` 标识（现：preset id `original_gnc`、`backend_kind=original_gnc`、`acceptance_level=EXPERIMENTAL_ORIGINAL_SOURCE`，见 [original_gnc/catalog.py](../../colav_simulator/original_gnc/catalog.py)）。不允许出现两侧共用同一 id 的"默认栈"。

## 后果

- 任何"同事栈支持/不支持"的对外表述必须给出原版后端的运行指针（run dir / manifest SHA）；给不出指针即视为没有结论。
- 成对比较运行是新增成本，但仅在登记册出现候选差异或需要沟通证据时触发，不是全矩阵常设。
- python 栈的修复不要求同步原版栈，反之亦然；两侧共享的只有场景定义与 VO/Fan/Mid 规划器代码。
- 8010 面继续承载日常迭代与产品演示；8014 面只做保真对照、集成验收与产品集成目标，不承担快速试错。
