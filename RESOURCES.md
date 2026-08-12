# COLAV Simulator 学习资源

## Knowledge

- [当前工作区源码](./colav_simulator/)
  本课程事实主来源。使用场景、仿真、Ship、算法集成、实验和评估模块的实际调用链。
- [项目 README 与上游仓库](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator)
  作者维护的模块说明、接口约定、生态依赖和强化学习入口。用于建立原始设计意图。
- [论文：Simulation Framework and Software Environment for Evaluating Automatic Ship Collision Avoidance Algorithms](https://doi.org/10.1109/CCTA54093.2023.10252863)
  Tengesdal 与 Johansen 的 CCTA 2023 原始框架论文。用于理解研究问题、仿真边界和评估定位。
- [Gymnasium：Create a Custom Environment](https://gymnasium.farama.org/main/introduction/create_custom_env/)
  官方环境设计指南。用于学习 observation、action、reward、termination、truncation 与环境校验。
- [Stable-Baselines3：Reinforcement Learning Tips and Tricks](https://stable-baselines3.readthedocs.io/en/v2.7.0/guide/rl_tips.html)
  官方实验建议。用于独立测试环境、归一化、评估和可复现实验设计。

## Wisdom (Communities)

- [项目 GitHub Discussions](https://github.com/ntnu-itk-autonomous-ship-lab/colav-simulator/discussions)
  向维护者核实接口意图、外部算法兼容性和研究复现边界。
- [Farama Discord](https://discord.gg/farama)
  Gymnasium 社区。用于验证自定义环境、向量化和 API 兼容问题。

## Gaps

- 当前分支新增的实验层、Web 控制面和能力分级尚无统一架构文档；课程将从源码持续维护参考图。
- 深度学习推理插件与训练环境之间的统一模型契约仍需在后续课程中实证梳理。

