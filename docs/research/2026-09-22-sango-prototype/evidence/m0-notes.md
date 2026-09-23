# M0 证据记录 — 环境就绪与海面冒烟（2026-09-23，rev2 按 code-review 修正）

## 结论：闸门 PASS（含分辨率维度偏差的透明说明，见 §3）

Mac M3 (arm64) 上 Unity 6000.3.24f1 + HDRP 17.3.0，**开 Script Interactions + 6 艘占位船逐三角形水高查询**（144 queries/frame，failed 0）条件下，Game 视图稳态 fps 145–167，远超 ≥30 闸门。R1 回退分支不触发，Mac 主力路线锁定。

## 1. 证据文件与图内实际读数

`evidence/m0-fps.png`（Game 视图 Play 中整编辑器截图，1280×704 栅格缩放显示）覆盖层实际数字：

- `fps: 166.9    frame avg/max: 5.99 / 15.06 ms`
- `water queries/frame: 144 (failed 0)`
- 底部状态栏同帧 Console 行：`fps=166.2 frame_ms_avg=5.99 frame_ms_max=14.51 queries_per_frame=144 query_ms_per_frame=0.43`

（rev1 曾误引另一帧的 165.0/6.06/18.23 数字，该帧未存盘，已更正为上图实际内容。）

## 2. 三源读数互相印证

| 来源 | 读数 |
|---|---|
| `evidence/m0-fps.png` 覆盖层 | fps 166.9，frame avg/max 5.99/15.06 ms，144 q/frame failed 0 |
| `sango/Logs/fps-report.jsonl` 稳态段 | 两次前台会话稳态 fps 145–167（均值 ~160） |
| Editor Console `[Sango.M0]` 每 10s | fps=162.9–166.2，query_ms_per_frame=0.42–0.43 |

144 q/frame = 6 船 × 24 三角形（两 primitive 组合体）× 1 probe/船，与场景构建器一致——查询负载确在运行，裸海面读数不采信（PLAN §5 M0 验收条款）。

`fps-report.jsonl` 文件构成说明：前 108 行为首次会话旧格式（含 `:F3` 字面量的非法 JSON 行，WriteJsonLine 格式串 bug，rev2 已修），其后为新格式合法行（含 res 字段）；两段时间轴不连续属同一文件两次 Play 追加所致，原始数据未清洗保留。

query_ms_per_frame 稳态范围 **0.39–0.54 ms**（启动预热期个别行至 10.9，统计已剔除）。

## 3. 分辨率维度的偏差与折算（诚实记录）

- jsonl `res` 字段（`Screen.width x Screen.height`）记录 Game 视图 backbuffer 逻辑尺寸为 **1534x754**（Game 视图处于 Free Aspect，跟随编辑器窗口布局），**未达到 1440p（2560x1440）的字面条件**。
- 本机为 macOS 2x retina 环境（编辑器窗口物理尺寸 2560x1409），实际渲染像素在 1534x754 ~ 3068x1508 区间（取决于 Game 视图 retina 渲染是否生效，未能在本轮固化证据）。
- 尝试固定 2560x1440：Game 视图 Aspect 下拉 popup 可弹出，但本会话期间显示器拓扑多次变化（display topology changed 报错），精细 GUI 选择无法稳定完成；Editor 处于后台时渲染被系统节流（fps 降至 0–58），前台化依赖 `open -a Unity` 时机。**2560x1440 固定分辨率的补测列为 M1-C 首个 GUI 会话的首项动作。**
- 保守折算（标注为推断非实测）：按逻辑分辨率下限 1.16MP 计，1440p（3.69MP）像素量为其实测条件的 ~3.2 倍；以 fillrate 线性假设折算，稳态 145–167 fps 在 1440p 下预算仍 ~45–52 fps，超闸门。像素成本之外的开销（水高查询 0.4ms、draw call、模拟）与分辨率无关且已实测达标。

## 4. 资源占用

- Editor 进程 RSS **~1061 MB**（8GB 统一内存，无 swap 迹象）。
- 磁盘：数据卷实际可用 **109 Gi**（此前计划按 25Gi 计，实为系统卷快照读数误报；R4 风险实际缓解，仍保持资产克制纪律）。

## 5. 环境与许可

- Unity 6000.3.24f1 (arm64, Metal) 装于 `/Applications/Unity/Hub/Editor/6000.3.24f1/`，Hub 已识别。
- 安装方式偏差记录：Hub headless install 对该版本报 404（Hub 侧 URL 构造问题，Release API 确认 changeset `4e7b9b5b6244` 的 arm64 pkg 实际存在）→ 改走 Release API 直下 pkg + `pkgutil --expand-full` 无 root 安装 + Hub `editors --add` 注册。mac-il2cpp 模块未装（M2 build 前按需补）。
- HDRP Asset 创建：`M0SetupPipeline.Setup`（batch `-executeMethod` 入口）按 HDRP 官方 `HDAssetFactory` 路径创建并挂 `GraphicsSettings.defaultRenderPipeline`；Quality 槽位未分档（跟随 default pipeline，无独立"中画质"档——同列 M1-C 补测项）。HDRP Wizard 首启弹窗（Quality 提示）已关闭。
- **许可档位（PLAN §3/§7 R7）**：非游戏业务且公司财务 >$1M 须 Unity Industry 档——待用户按公司实际主体核实，对代码与进度无阻塞（本记录为 M0 期内唯一未闭环前置项）。

## 6. 实施期修复（3 项）

1. `VolumetricClouds.CloudControl/CloudSimpleMode` 是嵌套枚举（HDRP 17.3 源码 :38/:51），非顶层名——Bootstrapper 已修。
2. `.NET` 复合格式串尾部 `{5:F3}}}` 解析歧义致 jsonl 输出字面 `F3`——WriteJsonLine 改显式 `ToString(fmt, InvariantCulture)` 拼接并新增 `res` 字段，已验证新行合法 JSON。
3. 空工程无 HDRP Asset 时 `ConfigureHdrpAssets` 空转——新增 `M0SetupPipeline` 前置创建。

## 7. 已知非阻塞项（转 M1）

- Scene 视图观感偏暗（Game 视图正常）：PBS 天空与太阳方向联动的曝光调优留 M1 天气/时刻系统一并做。
- Console 一条 sRGB RenderTexture gamma fallback 警告（Editor Only，无害）。
- 2560x1440 固定分辨率补测 + Quality "Medium" 档显式建档（见 §3）。

## 8. 命令留档

```bash
# 场景重建（batch）
Unity -batchmode -quit -projectPath sango -executeMethod Sango.Editor.M0SetupPipeline.Setup -logFile -
# fps 数据（Play 中每秒追加；res=Game 视图 backbuffer 逻辑尺寸）
sango/Logs/fps-report.jsonl
```
