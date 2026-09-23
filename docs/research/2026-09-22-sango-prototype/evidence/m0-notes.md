# M0 证据记录 — 环境就绪与海面冒烟（2026-09-23）

## 结论：闸门 PASS

Mac M3 (arm64) 上 Unity 6000.3.24f1 + HDRP 17.3.0，**开 Script Interactions + 6 艘占位船逐三角形水高查询**（144 queries/frame，failed 0）条件下，Game 视图稳态 **fps 145–167**，远超 ≥30 闸门。R1 回退分支不触发，Mac 主力路线锁定。

## 三源读数（互相印证）

| 来源 | 读数 |
|---|---|
| `evidence/m0-fps.png`（Game 视图覆盖层） | fps 165.0 / 166.9，frame avg/max 6.06/18.23 ms，water queries/frame 144 (failed 0) |
| `sango/Logs/fps-report.jsonl`（稳态段） | fps min/avg/max = 145–167（均值 ~160），query_ms_per_frame ≈ 0.41–0.45 |
| Editor Console（`[Sango.M0]` 每 10s） | fps=162.9–166.2，queries_per_frame=144，query_ms_per_frame=0.42–0.43 |

144 q/frame = 6 船 × 24 三角形（两 primitive 组合体），与场景构建器一致——查询负载确在运行，裸海面读数不采信（PLAN §5 M0 验收条款）。

## 资源占用

- Editor 进程 RSS **~1061 MB**（8GB 统一内存，无 swap 迹象）。
- 磁盘：数据卷实际可用 **109 Gi**（此前计划按 25Gi 计，实为系统卷快照读数误报；R4 风险实际缓解，仍保持资产克制纪律）。

## 环境（实际安装路径）

- Unity 6000.3.24f1 (arm64, Metal) 装于 `/Applications/Unity/Hub/Editor/6000.3.24f1/`，Hub 已识别。
- 安装方式偏差记录：Hub headless install 对该版本报 404（Hub 侧 URL 构造问题，Release API 确认 changeset `4e7b9b5b6244` 的 arm64 pkg 实际存在）→ 改走 Release API 直下 pkg + `pkgutil --expand-full` 无 root 安装 + Hub `editors --add` 注册。mac-il2cpp 模块未装（M2 build 前按需补）。
- HDRP Asset 创建：`M0SetupPipeline.Setup`（batch `-executeMethod` 入口）按 HDRP 官方 `HDAssetFactory` 路径 `CreateInstance<HDRenderPipelineAsset>()` 创建并挂 `GraphicsSettings.defaultRenderPipeline`；HDRP Wizard 首启弹窗已关闭（Quality 槽位未填不阻塞 M0，默认跟随 default pipeline）。

## 实施期修复（3 项）

1. `VolumetricClouds.CloudControl/CloudSimpleMode` 是嵌套枚举（HDRP 17.3 源码 :38/:51），非顶层名——Bootstrapper 已修。
2. `.NET` 复合格式串尾部 `{5:F3}}}` 解析歧义致 jsonl 输出字面 `F3`——WriteJsonLine 改显式 `ToString(fmt, InvariantCulture)` 拼接，已验证新行合法 JSON。
3. 空工程无 HDRP Asset 时 `ConfigureHdrpAssets` 空转——新增 `M0SetupPipeline` 前置创建。

## 已知非阻塞项（转 M1）

- Scene 视图观感偏暗（Game 视图正常）：PBS 天空与太阳方向联动的曝光调优留 M1 天气/时刻系统一并做。
- Console 一条 sRGB RenderTexture gamma fallback 警告（Editor Only，无害）。

## 命令留档

```bash
# 场景重建（batch）
Unity -batchmode -quit -projectPath sango -executeMethod Sango.Editor.M0SetupPipeline.Setup -logFile -
# fps 数据（Play 中每秒追加）
sango/Logs/fps-report.jsonl
```
