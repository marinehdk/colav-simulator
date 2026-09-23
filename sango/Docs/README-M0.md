# README-M0 — M0-C 执行手册（Unity 6.3 LTS + HDRP 海面冒烟）

本目录是 M0 代码骨架的暂存区（Unity `-createProject` 要求目标目录为空，故先落 tmp/，不入库）。
执行者目标：把骨架装进仓库 `sango/` 工程，跑出「Script Interactions 开启 + 6 艘船逐三角形水高查询」条件下的
Game 视图 fps，验收线 **≥30 fps @ 1440p 中画质（Mac M3）**。裸海面读数不算数。
验收与回退闸门见 `docs/research/2026-09-22-sango-prototype/PHASE1-PLAN.md` §5 M0。

骨架文件清单：

```
gitignore-template                        → 复制为 sango/.gitignore
Assets/Scripts/Runtime/TriangleBuoyancyProbe.cs   逐三角形水高查询负载（含每帧查询计数/耗时统计）
Assets/Scripts/Runtime/FpsProbe.cs                fps 聚合、左上角覆盖层、Logs/fps-report.jsonl
Assets/Scripts/Editor/M0SceneBootstrapper.cs      菜单 Sango/M0/Build Water Smoke Scene（一键建场景）
```

---

## 0. 前置确认

- [ ] Unity Hub 已装，**Unity 6.3 LTS Editor（6000.3.x）已安装**（M0-B 线负责安装，此处只确认）。
  确认命令：`ls "/Applications/Unity/Hub/Editor/"`（应有 6000.3.x 目录）。
- [ ] 磁盘余量 ≥ 25Gi（Editor 7–10GB + 工程 + Library 缓存；红线见计划 §7 R4）。
- [ ] 许可档位核实（计划 §3/§7 R7，不阻塞）。

## 1. 建空工程

`-createProject` 目标目录必须为空/不存在：

```bash
mkdir -p /Users/marine/Code/Colav-Simulator/sango   # 必须保持为空，若已有内容先停下确认
"/Applications/Unity/Hub/Editor/<6000.3.x>/Unity.app/Contents/MacOS/Unity" \
  -createProject /Users/marine/Code/Colav-Simulator/sango
```

- 预期：生成空工程（默认 Built-in 管线，无 HDRP），进程自动退出。
- 失败排查：目标目录非空会直接报错退出；Editor 路径不含空格也建议加引号。

**更省事的替代路径**：Hub 里 New Project 选「High Definition 3D」模板建到 sango/（模板自带 HDRP 资产与
质量档，可跳过第 2 步的 manifest + wizard）。二选一；下文按 CLI 空工程主路径写。

## 2. 挂 HDRP 包（CLI 空工程路径专用）

用文本编辑器打开 `sango/Packages/manifest.json`，在 `dependencies` 里加一行（版本必须与 Editor 配套）：

```json
"com.unity.render-pipelines.high-definition": "17.3.0"
```

（17.3.0 = Unity 6000.3 对应的 HDRP 版本，已从 Unity 官方仓库 6000.3 分支 package.json 核对。
若 Package Manager 解析失败，改用 Package Manager UI 里列出的 17.x 最高版。）

重新打开工程让包解析：首次导入会弹 HDRP 配置对话框 / 或菜单 **Window > Rendering > Render Pipeline Wizard**，
点「Create / Fix All」（生成各画质档 HDRP Asset 并挂到 Project Settings > Quality）。

- 预期：控制台无红色报错；`Project Settings > Quality` 各档的 Render Pipeline Asset 已填充；
  编辑器顶部出现 HDRP 菜单相关配置，场景渲染变成 HDRP 默认天空。
- 失败排查：wizard 没弹且没资产 → 手动开 wizard；解析失败 → 核对 Editor 版本与包版本匹配。

## 3. 装入骨架

```bash
cp -R tmp/sango-skeleton-m0/Assets sango/
cp tmp/sango-skeleton-m0/gitignore-template sango/.gitignore
```

（sango/ 首次入库前务必确认 `.gitignore` 生效：`git status --short` 不得出现 Library/、Temp/、Logs/。）

## 4. 一键建场景

打开工程，编译通过后，菜单点 **Sango/M0/Build Water Smoke Scene**。

- 预期（Hierarchy，全新场景）：
  - `Water Surface`（OceanSeaLake + Script Interactions ✓）
  - `Global Volume`（Profile = Assets/Settings/M0-GlobalVolumeProfile.asset，含 VisualEnvironment→PBS 天空、
    Physically Based Sky、Volumetric Clouds(Simple/Performance 低配档)、Water Rendering ✓）
  - `Directional Light`（旋转 50/-30/0，HDRP 自动作为太阳驱动 PBS 天空与太阳圆盘）
  - `Ships/Ship-0..5`（各挂 TriangleBuoyancyProbe + hull 12x3x4m + 上层建筑，两排间距 15m）
  - `Main Camera`（(0,8,-25) 望向船群，fov 60）
  - `M0 Fps Probe`
- 产物文件：`Assets/Scenes/M0-WaterSmoke.unity`、`Assets/Settings/M0-GlobalVolumeProfile.asset`。
- 失败排查：菜单报编译错 → 先看 Console 修编译（API 见各文件注释里的 17.3 文档 URL）；
  跑菜单前保存手头未保存场景（新建场景会丢弃当前未保存改动）。

## 5. 画质与工程设置确认

- [ ] `Project Settings > Quality`：选目标档（中画质），确认其 Render Pipeline Asset 非空；
  打开该 HDRP Asset 检查 Water 小节 **Support Water Surfaces ✓**、**Script Interactions = GPU Readback**
  （Bootstrapper 已对所有可解析到的 HDRP Asset 强制开启，此处只做目检）。
- [ ] Game 视图设 1440p：Game 视图左上角分辨率下拉 → 自由比例/自定义分辨率 2560x1440
  （若选项受限，Maximize on Play + 窗口铺满外接 1440p 屏亦可，但记录实际渲染分辨率）。

## 6. Play 采集

1. 点 Play。预期：海面可见（FFT 波浪）、PBS 天空 + 体积云、6 艘船静浮在水面线（M0 无浮力运动，只压查询负载）、
   左上角白色大字覆盖层实时显示 `fps / frame avg/max ms / water queries per frame / query ms per frame`。
2. 等 ≥30 秒让读数稳定（首几秒 GPU 回读链路未就绪，failed 次数可能 >0）。
3. 每秒一行追加写入 `sango/Logs/fps-report.jsonl`；Console 每 10 秒打一行 `[Sango.M0] fps=... query_ms_per_frame=...`。
4. 记录内存：`ps aux | grep -i "[U]nity" | awk '{printf "%s %.0f MB\n", $11, $6/1024}'`（记录 RSS 总量）。
5. 截图（含覆盖层读数 + Profiler 或覆盖层 fps）存
   `docs/research/2026-09-22-sango-prototype/evidence/m0-fps.png`；把 fps-report.jsonl 末尾若干行
   和 Editor RSS 记进同目录 m0-notes.md（或证据页）。
6. 停 Play。闸门：稳定 fps ≥ 30 → M0 过；< 30 或明显 swap → 触发计划 §5 R1 回退分支（降 HDRP 档 → a4000 评估），
   **不得带病过关**。

## 7. 故障对照表

| 现象 | 根因 | 处置 |
| --- | --- | --- |
| 水面粉红/品红 | HDRP 包版本与 Editor 不配套，默认水体材质缺失 | 回到第 2 步核对 17.x 版本；Reimport All；确认 HDRP Asset 已挂到 Quality 档 |
| 整个画面品红 | HDRP Asset 未挂到 Quality 档（wizard 没跑成） | 重跑 Render Pipeline Wizard，确认 Quality 槽位 |
| 什么都看不到（黑/纯天空无水） | ① HDRP Asset `Support Water Surfaces` 没开 ② Global Volume 的 Water Rendering 没勾 ③ 帧设置里 Water 被关 | ①② 由 Bootstrapper 强制，若被手动改动请重跑菜单；③ Camera/Global 帧设置加查 Water 位 |
| 覆盖层 `queries_per_frame = 0` | WaterSurface 的 Script Interactions 被关，或 HDRP Asset `waterScriptInteractionsMode` 未启用 | 重跑 Bootstrapper；目检 Water Surface 组件勾选与 HDRP Asset Water 小节 |
| `failed` 计数持续 > 0 | 回读数据未就绪（刚进 Play 的前几秒正常）或 scriptInteractions 关闭 | 等 30s 后仍 >0 再按上行处置 |
| 覆盖层不出现 | 场景里没有 M0 Fps Probe | 重跑 Sango/M0/Build Water Smoke Scene |
| fps-report.jsonl 没生成 | 工程目录只读 / Logs 被占 | 查 Console 的 `[Sango.M0] failed to write` 告警 |
| 菜单跑完提示场景丢失改动 | 当前未保存场景被 NewScene 丢弃 | 属预期（幂等重建）；先保存工作场景再跑 |

## 8. API 版本基线（代码注释中已内嵌出处）

全部按 **Unity 6000.3 / HDRP 17.3.0** 核对：`WaterSurface.ProjectPointOnWaterSurface(WaterSearchParameters, out WaterSearchResult)`
（注意 6000.3 的方法名是 `ProjectPointOnWaterSurface`，不是旧文档的 `ProjectOnWaterSurface`）、
`WaterSurface.scriptInteractions`、HDRP Asset `RenderPipelineSettings.supportWater / waterScriptInteractionsMode / supportVolumetricClouds`、
`WaterRendering.enable`、`VisualEnvironment.skyType = SkyType.PhysicallyBased(4)`、`VolumetricClouds.cloudSimpleMode = Performance`。
搜索参数 `error=0.01, maxIterations=8` 对齐官方 WaterSamples/Buoyancy.cs。若未来升 Unity 版本，先重跑一遍这些 API 的文档核对。
