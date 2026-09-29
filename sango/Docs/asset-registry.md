# Sango 资产登记表（asset-registry）

- 维护人：工程负责人 ｜ 建表：2026-09-28 ｜ 依据：docs/research/2026-09-24-scene-ship-fidelity/00-REPORT.md §2.1 合规动作
- 台账定位：sango/Assets 中所有第三方/地理来源资产的唯一登记处。

## 使用规则

1. **先登记，后入工程**：任何新资产（商店购买、免费包、vendored 二进制、AI 生成、自制/扫描模型）与地理数据（DEM、卫星影像、水深、矢量）在进入 `sango/Assets` 之前，必须先在下表登记一行：来源 URL、许可、署名文本三列缺一不可；查不到许可原文的资产不得合入。
2. **署名文本列**＝需要逐字展示在仿真器"关于"页/分发物中的文本；标"不适用"表示该许可无外部署名义务。
3. **入账日期**＝资产首次入库的 commit 日期（附短 SHA 便于溯源）。

## 数据红线（约束性，来源：00-REPORT §2.1 / dive_03 条款原文核实）

以下三类数据**可以在线查看，但一律不得提取为引擎资产**——不得下载缓存、不得烘焙进场景/网格/贴图/地形：

1. **Esri World Imagery** —— 条款限定"数据采集/编辑底图"用途；
2. **Google Photorealistic 3D Tiles** —— Map Tiles 政策明禁 "Geodata extraction" 与 "Offline uses"，叠加物不得派生；经 Cesium ion 的同一条款还将 **vessel navigations** 列入 High Risk（对船舶仿真器是双红灯）；
3. **MPA 新加坡 ENC（S-57）** —— 绑定 type-approved ECDIS 使用；视觉原型用 GEBCO + BATNAS 即可。

## 登记表

| 资产名 | 本地路径 | 来源URL | 许可 | 署名文本 | 入账日期 | 用途 |
|---|---|---|---|---|---|---|
| Kenney Watercraft Kit 2.1（3 FBX + colormap.png） | `sango/Assets/Art/KenneyWatercraft/` | 主页 https://kenney.nl/assets/watercraft-kit ；zip https://kenney.nl/media/pages/assets/watercraft-kit/a335cfed49-1713519620/kenney_watercraft-pack.zip （~1.9 MB） | CC0 1.0（`PROVENANCE.txt` 逐字记载，正文许可文本随库 `LICENSE.txt~`） | 无需署名（CC0 无强制义务）；自愿致谢：`"Watercraft Kit" by Kenney (kenney.nl) — CC0 1.0` | 2026-09-24（c4c2daee） | M2 交通船占位（ship-cargo-a / ship-ocean-liner / boat-fishing-small，LOA 100/60/12 m）+ 远景锚地船群 |
| NetMQ 4.0.1.13（NetMQ.dll，lib/netstandard2.0，未修改） | `sango/Assets/Plugins/NetMQ/NetMQ.dll` | https://github.com/zeromq/netmq | LGPL-3.0（根 `THIRD_PARTY_NOTICES.md` §"Sango FramePublisher vendored binaries" 逐字记载；全文随库 `LICENSE-NetMQ.txt`，含版权持有者 special exception）。版本 4.0.1.13 经 dll 内字符串逐字核实 | 分发时保留根 `THIRD_PARTY_NOTICES.md` 与 `LICENSE-NetMQ.txt`（LGPL §4 "prominent notice"）；库保持未修改、可替换，应用与库可分离（LGPL §4/§5）。Copyright (c) 2010-2018 NetMQ contributors | 2026-09-28（ecf33a72） | M3 FramePublisher（默认关闭的 ZeroMQ 帧发布） |
| AsyncIO 0.1.69（AsyncIO.dll，未修改） | `sango/Assets/Plugins/NetMQ/AsyncIO.dll` | https://github.com/somdoron/AsyncIO | MPL-2.0（`THIRD_PARTY_NOTICES.md` 逐字记载；全文 `LICENSE-AsyncIO.md`） | 未修改库连同 `LICENSE-AsyncIO.md` 一起分发即满足 MPL-2.0 file-level copyleft。Copyright (c) Somdoron Ltd. | 2026-09-28（ecf33a72） | NetMQ 依赖（同目录 vendored） |
| NaCl.Net 0.1.13（NaCl.dll，未修改） | `sango/Assets/Plugins/NetMQ/NaCl.dll` | https://github.com/somdoron/NaCl.net | MPL-2.0（`THIRD_PARTY_NOTICES.md` 逐字记载；全文 `LICENSE-NaCl.md`） | 同上，随库保留 `LICENSE-NaCl.md`。Copyright (c) Somdoron Ltd. | 2026-09-28（ecf33a72） | NetMQ 传递依赖（CurveZMQ 支持） |
| telemetry-sample.json（内部录制的传输 fixture） | `sango/Assets/Tests/Fixtures/telemetry-sample.json` | 无外部来源 —— 本机 uvicorn compact-v1 会话录制（run_id `bd4e1404-ac39-4986-b1ca-d50676d612b0`，场景 head_on，schema_version 1.0） | 内部录制，无外部许可 | 不适用 | 2026-09-28（ecf33a72） | M3 传输 golden fixture（DetectionResult / FramePublisher 测试） |
| Copernicus GLO-30（6 tile：N01/N00/S01 × E103/E104，共 115.6 MB，不入库） | `tmp/m6-spike-data/tiles/`（经 `tools/terrain/spike1.sh` 重下再生；判据产物见 `docs/research/2026-09-29-m6-terrain-spike/`） | https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{T}_DEM/Copernicus_DSM_COG_10_{T}_DEM.tif （AWS 公开镜像，匿名） | Copernicus "Full, Free & Open"（ESA 公开镜像合法分发） | © Copernicus DEM / ESA | 2026-09-29（本 commit，见 `tools/terrain/spike1.sh` 同批） | M6 地形 spike——海峡 DEM（岛屿起伏 0–303 m），海面 0 m 钳平；bathymetry 留 GEBCO 正式批 |

## 备注

- **NetMQ 许可口径**：询价指令原文写 "LGPL-3.0/MPL-2.0"；实际根 `THIRD_PARTY_NOTICES.md` 记载为 **NetMQ 本体 = LGPL-3.0**，MPL-2.0 属于随附的 AsyncIO 0.1.69 与 NaCl.Net 0.1.13。本表按"以 THIRD_PARTY_NOTICES 实际记载为准"逐 dll 拆分登记（故首批 5 条而非 3 条）。
- 后续采购到位的资产（配角包、CGTrader 45M、MicroSplat、Amplify Impostors 等）见 `docs/research/2026-09-24-scene-ship-fidelity/procurement-checklist.md` 表A，到货后逐条转入本表。
