# ChatGPT 旧交接方案审计（Win10 KVM + GPU 直通跑原版 Aeolus）

日期：2026-09-22。审计对象：`/var/folders/.../sango-sim-handoff-20260922-TrSSXG/HANDOFF.md`（已读到，276 行）。除 WebFetch 公开页面与 ssh 只读核查外，无任何逆向操作。

## 1. 三台设备可行性

**a4000 直通：技术可行，作为 P0 前置不合理。** 前提条件其实很好：GPU1（0000:06:00.0）IOMMU 组 16 仅含 GPU+音频两个功能，是理想直通形态（HANDOFF:120）。但代价结构失衡：为"亲眼看一次 EXE"需要未激活的 Windows（无产品密钥，HANDOFF:207）、6GB ISO、746MB 驱动（至今只下到 178MB 的 `.part`，ssh 核实仍在）、两次失败的 GPU 释放脚本（HANDOFF:14）、仅 127.0.0.1 的 VNC 链路（HANDOFF:136）、95% 满的根盘。更关键的是共享属性：GPU1 绑入 vfio 后对宿主永久消失，与后续主路线冲突——阶段 1–3 最可能的渲染/集成主机正是 a4000 上的 Linux（Unity Linux Editor、无头渲染、Colav 集成测试）。HANDOFF:124 还提到存在其他远程图形会话。结论：直通只能作为**一次性时间盒支线**，不能作为默认路径；VM 独占 16GiB 内存长期 running（ssh 核实 `domstate=running`）本身就在消耗共享资源。

**Mac 跑 EXE：不现实，放弃。** 官方最低要求 Win10 x64 + DX12 (SM5.1) + 6GB VRAM + 16GB RAM（releases 页核实）；Mac 是 M3 8GB（HANDOFF:106）。需 x86 转译 × D3D12→MoltenVK 双层转换，HDRP 海面场景在这条链上成功率极低，8GB 统一内存也不够。此条为基于公开系统要求与图形栈事实的推断，未实测（也不值得实测）。付费云 Windows 违背免费偏好，不推荐。

**EXE 改造上限：只是"基准参照物"。** README 明示 binary-only、"source code may become available in the future"（仓库页核实）；仓库根仅 LICENSE/README/citation.cff。合法用途上限 = 运行、观察、截图录屏、读 player log。不能改行为、不能嵌 Colav、不能做同帧采集接口、不能提取资产（既因不做逆向，也因 ZIP 内第三方资产许可未公开声明——推断）。HANDOFF 自己的判断"不把原版二进制当可插拔后端"（HANDOFF:44）正确，保留。**既然上限只是"看"，为其建整套直通基础设施的投入产出比就是本方案的核心缺陷。**

## 2. 保留 / 放弃 / 替换

| 项 | 处置 | 理由 |
|---|---|---|
| P0"体验原版建立视觉基准"的目标 | **保留**，降为可选支线 | 视觉基准有价值，但不值一周基建 |
| 阶段 1A/1B 独立 Unity 工程路线（HANDOFF:37-38,45-49） | **保留** | 与主路线一致，是正路 |
| 三条责任原则：不另写 COLREG 裁决 / 真值留评价通道 / 状态自由度不双积分（HANDOFF:53） | **保留** | 正确的架构边界 |
| run-guide、参数表等调研文档 | **保留** | 在任何 Windows 机器上跑都复用 |
| 已校验的 Aeolus ZIP（268MB，ssh 核实在盘） | **保留备用** | 将来找到 Windows 机器即开即跑 |
| Win10 KVM + GPU1 直通作为 P0 默认必经路径 | **放弃默认地位** | 见 §1；若保留只能时间盒化 |
| "先装完 Windows 再做其他"的串行依赖（HANDOFF:8） | **放弃** | 改为阶段 1A 立即并行起步 |
| 现有 VM 处置 | **建议立即正常关停** | 释放 16GiB；磁盘保留，不删（92G 可用，不急） |

## 3. Aeolus 仓库合法可利用信息（全部公开页面核实）

- **LICENSE = BSD-3-Clause**（GitHub 仓库页标注 + 根目录 LICENSE）。允许使用/再分发仓库内容（保留版权声明）。注意：BSD-3 覆盖仓库与 release 包本身是合理推断，但**不自动延伸**到包内第三方资产（船模、纹理），其许可未公开声明。
- **README 的 4 个演示 GIF + 昼夜截图**：正好覆盖参考画面 1/3/4（COLREG 遭遇、夜间航行灯）；GIF 注明"slightly sped up"，帧率不能当性能参照。
- **参数表**（environment/waypoint/island/sensor）：参考画面 2 的 Simulation 面板可直接对照设计。
- **系统要求与 release notes**：Unity 2022.2.5f1（与论文交叉验证）；v1.11 已修 loading 冻结、空格键开 console；最低 6GB VRAM 可作阶段 1A 性能预算下界参照。
- **已知问题**：`Generate Island Per Environment` 卡死需禁用；局限：仅 motorboat 单船型、泡沫简化。
- **citation.cff**：引用格式（Vekinis & Perantonis 2023）。
- **机会**：README 承诺兴趣足够可能开源——值得 watch 仓库；若开源，阶段 1 可直接参考其 HDRP 实现（推断性机会，非承诺）。

## 4. 修订后"前置体验"最小路径（全部可选，不阻塞阶段 1）

1. **零成本（默认）**：论文场景描述 + README 的 GIF/截图 + 4 张参考画面 → 冻结一份"视觉基准卡"（镜头清单、明暗/天气/参数对照），直接供阶段 1A 使用。当天完成。
2. **低成本（推荐补做）**：找任意现成 Windows+NVIDIA 机器（个人 PC / 同事工作站），拷 ZIP 跑 30–60 分钟，按 run-guide 录屏截图。半天级工作量，无 VM、无直通、无激活问题。
3. **兜底**：前两者不可得时，a4000 时间盒——与其他用户协调一个窗口，一次会话内完成"直通→运行→录屏→删 VM→归还 GPU1"；可从当前许可页接续，但目标降为"能跑 EXE 即可"，不追激活。VM 关停前不得开始直通操作。
4. **不做**：Mac Wine/CrossOver；付费云 Windows。

阶段 1A 不等待以上任何一项：Mac 上直接起 Unity 工程，用论文参数（Tessendorf/JONSWAP/LOD）先行，原版素材到位后再回头对照。

## 来源

- HANDOFF.md（本机临时目录，行号见文中）
- https://github.com/aavek/Aeolus-Ocean 与 /releases（WebFetch，2026-09-22）
- `ssh a4000 'ls -la ~/aeolus-vm/assets; virsh domstate aeolus-win10; df -h /'`（只读，2026-09-22：ZIP 268,258,577B 在盘；VM running；根盘 95%、可用 92G）
