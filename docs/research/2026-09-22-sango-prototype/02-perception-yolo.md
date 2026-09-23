# 阶段1感知链路调研：YOLO 识别 + 避碰演示的最小支撑

- 日期：2026-09-22 ｜ 调研员：感知链路调研员（动态工作流子任务）
- 问题：阶段1纯展示 Prototype 的画面如何低成本支撑"未来 YOLO 识别 + 避碰演示"，并给阶段2（Colav-Simulator 后端闭环）留缝。

## TL;DR 推荐主线

阶段1**不接任何推理**：船体 3D 位置本引擎已知，用 `Camera.WorldToScreenPoint` 每帧把船包围盒投影到屏幕，画出检测框叠加层（UI 线框 + 类别/置信度标签）。同时落两颗"留缝"钉子：①独立封装 `DetectionOverlay` 组件，接口只认"帧 + 框列表"，不关心框来源；②封装 `FramePublisher`（ZeroMQ PUB，JPEG 帧）采集相机画面。演示升级路径为三级：真值框（零成本）→ Mac 本机 Sentis 引擎内推理（可选）→ a4000 Python+YOLO 外部推理（阶段2形态，框经 FastAPI/WebSocket 进 Colav 后端）。理由：阶段1的目标是画面效果，YOLO 检测不增加演示信息量；把"能演示"与"能升级"解耦，工作量最小且无回退成本。

## 1. Unity Perception 现状：已停更，不复刻其流程

- **已停更**：官方仓库 README 明确 "This project has been discontinued and is no longer supported by Unity"（[com.unity.perception](https://github.com/Unity-Technologies/com.unity.perception)，本次 WebFetch 核实）。最后发布版 **1.0.0-preview.1（2022-11-22）**，从未出 stable（本次 `gh api repos/Unity-Technologies/com.unity.perception/releases` 实查）。
- 能力（历史事实）：HDRP/URP 均支持（仓库含 PerceptionHDRP 示例）；随机化工具链完整；原生输出 SOLO 格式，经 `pysolotools` 转 COCO。
- 版本风险：README 兼容徽章停在 Unity 2021.3/2022.1（同上 WebFetch）。未验证其可装入 Unity 6——**推断大概率不兼容**，需锁旧编辑器才能用。
- **结论**：论文式 Perception 课程流程不复刻。阶段1自建场景中船位真值已知，真值框用 `WorldToScreenPoint` 投影自产，比 Perception 更轻且无版本枷锁；批量产训练集时同样走"渲染 + 自写真值导出（COCO/YOLO txt）"，Perception 仅作为可选参考。

## 2. 引擎内推理：Sentis 可用，但不是阶段1主线

- **现状**：Barracuda 已死，接替者为 `com.unity.ai.inference`。最新 **2.6.1（2026-04-02）**，displayName 已改回 "Sentis"，**要求 Unity 6000.0**（本次 `gh api repos/needle-mirror/com.unity.ai.inference` + package.json 实查）。**Unity 2022.3 LTS 封顶 Sentis 2.1.3**（[官方文档](https://docs.unity3d.com/Packages/com.unity.sentis@2.1/manual/index.html)：opset 7–15，全平台）。→ 新项目应直接上 Unity 6。
- **YOLO 支持**：官方 Hugging Face [unity/inference-engine-yolo](https://huggingface.co/unity/inference-engine-yolo)（GPL-3.0）提供 YOLOv8/9/11/12 的 n/s ONNX，配 `RunYOLO.cs` 示例；模型导出 `nms=False`，**NMS 需 C# 后处理**；示例用 `BackendType.GPUCompute`。注意底层模型源自 Ultralytics（AGPL-3.0），商用需评估许可证。
- **后端与平台**：三后端 GPUCompute（compute shader，走 Metal/Vulkan/D3D12）/GPUPixel（无 compute shader 时的回退）/CPU（Burst）（[Sentis 创建引擎文档](https://docs.unity3d.com/Packages/com.unity.sentis@1.6/manual/create-an-engine.html)）。**无 CUDA 直连**——a4000 无头 Linux 服务器跑不了"Unity 渲染 + Sentis GPU"，引擎内推理只能在 Mac（Metal，M3 8GB）或带显示的机器上做。
- **阶段1判断**：论文用 Barracuda+YOLOX-S 引擎内推理（见任务书已核实论文事实），路线本身可复刻；但 Mac 上 HDRP 海面渲染已吃满 GPU/内存预算，再叠推理有帧率风险（推断）。故引擎内推理降为**可选 A 线**（演示升级时再做），不进主线。

## 3. 引擎外桥接：成熟做法与延迟量级

| 环节 | 实测/来源 | 数值 |
|---|---|---|
| JPEG 编码 640×480 q80 | 本机实测：项目 venv `cv2 4.11.0` | **0.84 ms/帧，≈200 KB** |
| localhost TCP 200 KB 往返 | 本机实测同上 | **0.07 ms** |
| Mac→a4000 网络单程 | 本机实测 `socket.connect('a4000',22)` ×20 | **中位 2.1 ms** |
| Unity GPU→CPU 读回 | 官方 [AsyncGPUReadback API](https://docs.unity3d.com/ScriptReference/AsyncGPUReadback.html)：无阻塞但**引入约 1 帧延迟** | ~16.7 ms @60fps |
| YOLO GPU 推理（公开值） | [Ultralytics 检测文档](https://docs.ultralytics.com/tasks/detect/)：YOLO26n 640px，T4+TensorRT **1.7 ms**，CPU 38.9 ms | a4000 上个位数 ms（推断） |

合成估计：全链 ≈ 1 帧 + 5–15 ms，**10–20 Hz 叠加刷新可稳定演示**（推断，未做端到端实测）。

开源参考实现（2 个）：
1. [offchan42/Unity3D-Python-Communication](https://github.com/offchan42/Unity3D-Python-Communication)（MIT）：Unity C#（NetMQ）↔ Python（PyZMQ）ZeroMQ REQ/REP 通用模板，作者称可到万次请求/秒；无图像管线，需自行加 JPEG 帧（本次 WebFetch 核实）。
2. [Unity-Technologies/Unity-Robotics-Hub](https://github.com/Unity-Technologies/Unity-Robotics-Hub)（Apache-2.0，活跃）：传感器图像出 Unity 的官方级参考；旧 ROS-TCP-Connector/TCP endpoint 已归档，新方向为 Simulation Pro（Unity 6.3+）（本次 WebFetch 核实）。另有旁证：论文所用 ML-Agents 以 gRPC 承载 32 agent 并行相机观察（任务书已核实的论文事实），证明该形态可承载数十路帧流。

## 4. 推荐主线与备份线对比

- **主线（推荐）**：真值框叠加（零推理）+ `DetectionOverlay`/`FramePublisher` 两钉子。阶段2切换时，检测框由 a4000 上 Python+YOLO 产生，经 **Colav-Simulator 现有 FastAPI/WebSocket** 下发——后端 `gui_server/main.py:31` 已 import WebSocket，`main.py:1658` 已建 FastAPI app，叠加层与后端闭环共用一条消息总线，Unity 侧零改动。
- **备份线（引擎内 Sentis，可选 A 线）**：Mac Metal 跑 YOLOv8n，自包含、零网络；代价是 Unity 6 锁定、NMS 手写、Mac 资源竞争、且与阶段2的 a4000/Colav 形态不一致（到时还得做外部推理）。**优于备份线的原因**：主线每一行工作（overlay 组件、帧发布、消息格式）都被阶段2直接复用，备份线有一半工作（C# NMS、Metal 调优）到阶段2即废弃。a4000 直接上线（跳过真值框）作为负备份：引入跨机部署复杂度，对阶段1画面目标零增益。

## 5. 合成数据→海事 YOLO 微调：保留为可选项

- **可行性**：保留，优先级低于主线。数据管线：Unity 场景按论文课程（方位 45° 步进 × 俯仰 × 距离 5/20/50 倍船长 × Beaufort 1/3/6.5/9 × 晨午暮）批量渲染，同时导出投影真值框（COCO 或 YOLO txt，自写导出器，量级 1–5 万帧即可支撑 n/s 模型微调，推断）。
- **真实域补充**：公开集 [SeaShips](https://github.com/jiaming-wang/SeaShips)（31,455 张、6 船型，IEEE Shao 2018，有 COCO 兼容版）与 [Singapore Maritime Dataset](https://sites.google.com/site/dilipprasad/home/singapore-maritime-dataset)（1080p 视频）可混入防仿真偏置。
- **训练资源**：a4000 GPU1 空闲 16GB（`docs/research/2026-09-22-sango-prototype/03-hardware.md:31,40`），ultralytics 微调一夜量级可完成（推断，未实测）。

## 来源汇总

- 事实（本次会话 WebFetch/gh api 核实）：com.unity.perception README 与 releases；com.unity.ai.inference 2.6.1 package.json；docs.unity3d.com Sentis 2.1.3 overview / create-an-engine；huggingface.co/unity/inference-engine-yolo；docs.ultralytics.com/tasks/detect；docs.unity3d.com AsyncGPUReadback；offchan42 与 Unity-Robotics-Hub 两仓库 README。
- 实测（本次会话执行的命令）：`.venv/bin/python` JPEG 编码与 localhost TCP 往返基准；`python3` 对 a4000:22 的 TCP 连接时延 ×20；`gh api` 两包版本查询。
- 本仓库证据：`gui_server/main.py:31,1658`；`docs/research/2026-09-22-sango-prototype/03-hardware.md:24-52`。
- 来自任务书的已核实论文事实：Aeolus 用 Barracuda+YOLOX-S 引擎内推理、ML-Agents 32 agent、Perception 课程参数。
- 明确未验证项：Perception 1.0-preview 在 Unity 6 的可安装性；a4000 上 YOLO 实测推理延迟；端到端 Unity→a4000→Unity 帧回路延迟。
