# 三台设备只读盘点（阶段1 硬件底座）

- 日期：2026-09-22
- 盘点人：硬件盘点员（dynamic-workflow subagent）
- 性质：**全部只读命令**（cat / uname / nvidia-smi / lscpu / free / df / docker info / dpkg -l / ls / ps），未在远端安装、修改、删除任何内容；未扫端口、未改任何配置。
- 结论区分：标注【事实】= 本session实测输出；【推断】= 基于事实 + 公开常识的判断，未实测。

---

## A. 每设备事实清单

### A.1 Mac 本机（开发机）

| 项 | 命令 | 关键输出 |
|---|---|---|
| 机型/芯片 | `system_profiler SPHardwareDataType` | MacBook Pro, Mac15,3, **Apple M3**, 8 核 CPU (4P+4E), **内存 8 GB** |
| GPU | `system_profiler SPDisplaysDataType` | Apple M3 GPU, **10 核**, Metal 4 支持；外接屏 2560x1440 |
| 系统 | `sw_vers` | macOS **26.6.2** (25G83) |
| 磁盘 | `df -h /` + `df -h /System/Volumes/Data` | 系统卷 460Gi；数据卷 **410Gi 已用 / 25Gi 可用（95% 满）** |
| Unity Hub | `ls /Applications` + `ls /Applications/Unity/Hub/Editor` | `Unity Hub.app` 已装；`/Applications/Unity/Hub/Editor` **存在但为空**（目录时间戳 2026-09-22 17:31），未找到任何 `Unity.app` → **Hub 已装、Editor 未装** |

【事实】要点：8GB 统一内存 + 25GB 剩余磁盘是本机两条硬约束。

### A.2 a4000（公司服务器）

ssh 连通：`ssh a4000 echo CONNECTED $(hostname)` → `tigerwang-System-Product-Name`，往返 **0.19s**（`/usr/bin/time -p`）。

| 项 | 命令 | 关键输出 |
|---|---|---|
| 系统 | `cat /etc/os-release` / `uname -r` | Ubuntu **22.04.5 LTS** (jammy)，内核 **6.8.0-124-generic** |
| GPU | `nvidia-smi` | **2× NVIDIA RTX A4000，各 16376MiB (16GB)**；驱动 **535.309.01**（CUDA 上限 12.2）；GPU0 已用 5248MiB，GPU1 仅 9MiB |
| GPU 占用 | `nvidia-smi --query-compute-apps...` | GPU0 上 3 个他人 python 进程（`/home/jeff.wu/prj_MinerU/.venv`、`prj_Embedding/.venv`，合计约 5.2GB）→ **共享机器** |
| CPU | `lscpu` | x86_64，**i7-12700**，12 核 20 线程 |
| 内存 | `free -h` | **125Gi 总量**，已用 38Gi，可用 84Gi |
| 磁盘 | `df -h` | 根卷 LVM **1.8T，已用 95%，仅剩 92G** |
| Docker | `docker --version` / `docker info` | Docker **29.1.3**；Runtimes: `io.containerd.runc.v2` **`nvidia`** `runc` → **nvidia runtime 已就绪**；默认 runtime 仍为 runc |
| CUDA 工具链 | `nvcc --version` | **command not found**（裸机无 CUDA toolkit，仅驱动；容器内可自带） |
| 图形栈 | `ps aux` + `systemctl get-default` | Xorg + gnome-shell 在跑（GDM），默认 `graphical.target` → 有 X server 可用 |

【事实】要点：**双 A4000 16GB**（比任务书预估"单卡"多一张）；GPU1 基本空闲；根盘剩余空间紧张（92G）；多人共享。

### A.3 agx（Jetson 主机）

ssh 连通：`ssh agx echo CONNECTED $(hostname)` → `ubuntu`，往返 **0.29s**。

| 项 | 命令 | 关键输出 |
|---|---|---|
| 型号 | `cat /proc/device-tree/model` | **NVIDIA Jetson AGX Orin Developer Kit** |
| JetPack/L4T | `cat /etc/nv_tegra_release` | **L4T R36.4.4**（2025-06-16 构建），aarch64 → 属 JetPack 6.x 系列（精确小版本未在机上确认，见下） |
| 系统/内核 | `cat /etc/os-release` / `uname -r` | Ubuntu 22.04.5 LTS，内核 5.15.148-rt-tegra（PREEMPT_RT 实时变体） |
| CUDA | `ls /usr/local/cuda*/version.json` | **CUDA SDK 12.6.11** 已装（`/usr/local/cuda-12.6`）；`nvcc` 不在 PATH 但 toolkit 在；`nvidia-smi` 驱动 540.4.0 / CUDA 12.6 |
| GPU | `nvidia-smi --query-gpu=name...` | `Orin (nvgpu)`（iGPU，统一内存，容量报 N/A） |
| CPU | `lscpu` | aarch64，**12 核 Cortex-A78AE** |
| 内存 | `free -h` | **61Gi 统一内存**（64GB 版），另 30Gi swap |
| 磁盘 | `df -h /` | NVMe **915G，已用 52%，剩 424G** |
| Docker | `docker --version` / `docker info` | Docker 29.1.3；Runtimes: `runc io.containerd.runc.v2` → **无 nvidia runtime**；`which nvidia-ctk nvidia-container-runtime` 均未找到、`dpkg -l | grep -cE "nvidia-container|nvidia-docker"` = **0** |
| JetPack 元包 | `dpkg -l | grep nvidia-jetpack` | 无输出（元包未以该名安装；L4T 组件实际在位，CUDA 12.6 可用） |

【推断】L4T 36.4.x 对应 JetPack 6.2 系列（NVIDIA 版本映射），精确号未在设备上核实。
【事实】要点：aarch64 架构；CUDA 12.6 toolkit 在位但 **GPU Docker 链路缺 nvidia-container-toolkit**。

### A.4 三机互联

【事实】Mac → a4000 与 Mac → agx 两条 ssh 均免密连通（BatchMode），echo 往返分别 0.19s / 0.29s。未做其它探测（按任务约束未扫端口）。

---

## B. 能力矩阵

| 能力 | Mac M3 8GB | a4000 (2×A4000) | agx Orin 64GB |
|---|---|---|---|
| Unity Editor 可安装 | ✅ 已装 Hub，Editor 未装；Apple Silicon 原生支持【事实+公开常识】 | ✅ Linux x86_64 版 Editor 支持；有 Xorg/GDM【事实】 | ❌ Unity 无 aarch64 Linux Editor【推断：Unity 官方仅发 Win/macOS/Linux x86_64】 |
| HDRP 海面场景编辑 | ⚠️ 可装可跑但 8GB 统一内存极紧，Tessendorf HDRP 项目常规需 16GB+，预计频繁 swap【推断，未实测】 | ✅ 125GB RAM + 独显，最稳的编辑/烘焙环境【推断】 | ❌ 不适用 |
| 构建 Linux 版本 | ✅ 可从 Mac 交叉出 Linux build（Unity 支持跨平台 build target）【公开常识，未实测】 | ✅ 本机构建最直接 | ❌ |
| Headless 渲染 | ⚠️ 未实测；Unity `-batchmode -nographics` 可构建，出图需另配 | ✅ 最可行：Xorg 在跑可跑 GUI/离屏，Vulkan/EGL 离屏渲染可行【推断，未实测】；-nographics 构建链路标准【常识】 | ❌ 无 Unity |
| YOLO 推理 | ⚠️ 可跑小模型（PyTorch MPS/CoreML），8GB 内存限制 batch 与并发【推断】 | ✅ **主力**：2×16GB VRAM，Docker nvidia runtime 已配，拉 cu121 镜像即得 CUDA toolkit（裸机 nvcc 缺失不再是问题）【事实+推断】；驱动 535 → 容器 CUDA ≤12.2，主流 PyTorch/ONNXRuntime/TensorRT 镜像均覆盖【常识】 | ✅ 阶段3 边缘推理候选：CUDA 12.6 toolkit 在位，**TensorRT 是 Orin 正道**；但 GPU Docker 需先装 nvidia-container-toolkit（本次未动）【事实】 |
| Colav-Simulator Python 后端 | ⚠️ 能跑但挤 8GB | ✅ **首选宿主**（125GB RAM、20 线程） | ✅ 备选（61GB 统一内存充裕，aarch64 需依赖可装） |
| 磁盘余量 | 🔴 仅 25Gi（装 Editor ~7-10GB + 项目 + 资产会顶到） | 🟡 92G（够 1 套 Editor+项目，别放大资产库） | 🟢 424G |

未验证项（如实声明）：三台设备均**未实际安装/运行** Unity Editor、YOLO 模型或 headless 渲染做验证；以上为基于实测硬件事实的判断。

---

## C. 硬件分工建议

**阶段1（Prototype）**
- **开发机 = Mac**：写代码、Unity 编辑、git；受 8GB/25Gi 约束，海面资源从简（先 URP 或低配 HDRP），重资产放服务器。第一步需在 Mac 装 Editor（Hub 已就绪，Editor 未装）。
- **渲染/构建机 = a4000**：Linux 版 Editor + `-batchmode` 出 Linux build、离屏截图/录屏、后续若有 Unity 侧 ONNX 识别也在其 GPU 上跑。
- **推理机 = a4000**：Docker nvidia runtime 已就绪，YOLO 检测容器直接可用；优先用 **GPU1（空闲 16GB）**，GPU0 已被同事占用 ~5.2GB。
- **注意**：a4000 是共享机（他人进程、根盘 95% 满），放任何大资产前先协调并清理配额。

**阶段2（接入 Colav-Simulator 后端）**
- **后端宿主 = a4000**：Python 后端 + Unity 前端同机部署（125GB RAM / 20 线程），回路延迟最低；Web GUI 经局域网暴露给 Mac 浏览器。agx 可作第二后端节点/回放验证机（61GB 内存充裕）。

**阶段3（传感器闭环 + 边缘部署）**
- **边缘候选 = agx Orin 64GB**：TensorRT 化 YOLO + 传感器接入（aarch64、CUDA 12.6、424G 磁盘、RT 内核）。前置条件：安装 nvidia-container-toolkit 才能容器化 GPU 推理（本次只读未装）。
- 训练/微调（若做合成数据 YOLO 微调）放 a4000 GPU1 或租云；Mac 不承担训练。

**一句话**：Mac 出创意与代码，a4000 出算力（渲染+推理+后端），agx 守阶段3 边缘。
