# Original GNC 2026-08-24 本地后端

从固定的 `L4-5_source_only_20260824_v2` 快照校验并提取原 C++ 业务类。`native_context.hpp` 提供显式时钟、参数、类型化发布队列；本地库不链接 ROS2。四个原 Python 策略/观察模块在构建时提取为普通 Python 类。

当前验证平台为 macOS ARM64。A4000 上的原 ROS2 节点只生成独立参考，产品运行不连接该机器。源码清单 SHA256：`2c863347de59474a32d26a53d5631ed9a5b376623cd88d6fb83ca8173fc09411`，183 个声明文件。源资产仍需保留，仓库不附带同事整个平台。

## 当前产物

工作目录：`/Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration`。

- 默认指针：`build/original_gnc-current` → `original_gnc-glibc-v8`。
- 已验证库 SHA256：`6e9f2728758b7934296e8da9bfee1a98905e038b29402c6e95ae780c6dc220fa`。
- 既有 `build/original_gnc` 和早期失败/比较产物保留；不要覆盖其 manifest。
- 产品入口：Config → GNC Stack → **Original GNC · 2026-08-24**；Environment OFF/ON 分别执行 10/14 个原业务模块。
- 原 GNC 可用不代表避碰场景通过。当前原更新保护拒绝了受测避碰参考；详细边界见研究报告。

## 从固定快照重建

以下是本机已使用的依赖路径。其他机器先提供同一快照、Eigen **3.4.0**、nlohmann JSON、项目 Python 依赖及 C++17 编译器，再替换路径。

```sh
cd /Users/marine/Code/.worktrees/Colav-Simulator/original-gnc-integration
GNC_PYTHON=/Users/marine/Code/Colav-Simulator/.venv/bin/python
GNC_SOURCE_DIR=/Users/marine/Code/external_sources/L4-5_source_only_20260824_v2
GNC_DEPS_DIR=/Users/marine/Code/external_sources/original_gnc_build_deps
GNC_BUILD_DIR="$PWD/build/original_gnc-rebuild-01"
PYTHONPATH=. "$GNC_PYTHON" tools/original_gnc/build_native.py \
  --source "$GNC_SOURCE_DIR" --dependencies "$GNC_DEPS_DIR" \
  --output "$GNC_BUILD_DIR"
COLAV_ORIGINAL_GNC_BUILD="$GNC_BUILD_DIR" PYTHONPATH=. "$GNC_PYTHON" \
  -m uvicorn gui_server.main:app --host 127.0.0.1 --port 8014
```

构建器拒绝覆盖已有构建 manifest。显式 `build_directory` / `source_root` 或 `COLAV_ORIGINAL_GNC_BUILD` / `COLAV_ORIGINAL_GNC_SOURCE` 可指定其他位置；缺少快照、资产或有效库时后端不可用，不退回现有 Full Stack。

## 保真边界

- 保留原方程、系数、保护、积分器、降级逻辑；船体速度使用原 RK4，位置沿用原更新顺序。
- 内部按原注册周期与回调因果顺序执行：船体 0.02 s、控制 0.1 s、导引 0.5 s；分配保留原回调触发。外部通信步长不替代内部周期。
- Apple ARM 对齐原 GCC/Eigen 运算顺序、随机样本对顺序及作用于本库内部的数学函数。说明与许可证见 `reference_math/GLIBC-NOTICE.md`；不导出全局 C 数学替代符号。
- 原 launch 未启用的传感器融合、NDO、mission/safety 主链不自动启用。ROS 可视化/传输设施不作为本地控制模块。
- 原船体是本船唯一积分来源；开启原环境时，原聚合器是本船唯一环境载荷来源。

## 验证与报告

固定输入、边界、原生自由闭环、共同调度闭环、实际产品场景分别留证。构建成功和短测通过不能代替其余层次。

- [测试集成方案](../../docs/research/2026-09-10-original-gnc-test-integration-plan.md)
- [原版运行报告](../../docs/research/2026-09-10-original-gnc-source-runtime-report.md)
- [嵌入保真报告](../../docs/research/2026-09-10-original-gnc-fidelity-report.md)
- [避碰集成报告](../../docs/research/2026-09-10-original-gnc-integration-report.md)
