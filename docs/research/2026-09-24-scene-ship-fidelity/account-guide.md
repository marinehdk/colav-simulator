# 免费路线人闸操作指南（路线 A，2026-09-29 用户裁决）

目的：一次性完成所有免费注册/下载，解锁 M5 船队导入批与 M6 正式批。按优先级排序，逐项完成后告知进度即可。

## 1. Sketchfab（解锁 M5 船队 —— 最高优先级）

- **直达注册**：https://sketchfab.com/signup （免费，邮箱即可；下载功能需登录态）
- 注册完成后**下载以下 9 件**（均为 CC-BY 4.0，已核许可：可商用、须署名、无 AI 限制条款）：
  - 每件打开页面 → 右侧 **Download 3D Model** → 优先选 **glTF**（zip）或 GLB；若 "Original" 里有 FBX 则更佳 → 解压后放入 `sango/Assets/Art/Purchased/<船名>/`（目录名用下表短名）
- **下载清单**（主角船两件都下）：

| 短名 | 模型 | 面数 | 用途 |
|---|---|---|---|
| fishing-trawler | https://sketchfab.com/3d-models/trawler-421f3239115c44539686fcb62835f115 | 5.3k | 渔船（剪影-中远） |
| cargo-container | https://sketchfab.com/3d-models/container-ship-aaa41cca946b4a08bc08cf692b7757be | 189k | 集装箱船（中景，需减面） |
| cargo-general | https://sketchfab.com/3d-models/cargo-ship-b7c97df584824ca682d26daabf401f87 | 73k | 杂货船（中景） |
| tanker-suezmax | https://sketchfab.com/3d-models/tanker-ship-96ebf61af42b4062ae98a6ad848e1a25 | 193k | 油轮（中远） |
| tanker-lng | https://sketchfab.com/3d-models/lng-ship-fa335b96450d4344863bbf5d912a0288 | 90k | LNG 船（中远，同作者成对） |
| tug-rastar3200 | https://sketchfab.com/3d-models/rastar-3200-tugboat-1bbadbe4ab0a4b2599cd3f450942e6fe | 47k | 拖轮（中景） |
| fcb-houbei | https://sketchfab.com/3d-models/type-22-missile-boat-d90464e6ca2e4d23a7a5a9865d220945 | 17.8k | FCB 占位主选（42m，换白壳绿装） |
| fcb-pc3 | https://sketchfab.com/3d-models/lowpoly-uss-hurricane-pc3-9582af31655d43ddbb0d3d2af9a037eb | 14.5k | FCB 副选/远景（55m 巡逻舰） |

- 免登录补充（无需账号，顺手可下）：Quaternius 低模船包 CC0 副本 https://opengameart.org/content/lowpoly-ship-pack （远景填充）。
- ⚠ 只下这 8+1 件调研核证过的；Sketchfab 上同名/相似件多有"not mine/ripped"来源链风险（调研档案 §6 禁入清单），勿自行扩选。

## 2. Copernicus Data Space（解锁 M6 的 S2 卫星贴图）

- **直达注册**：https://dataspace.copernicus.eu/ → Register（免费；邮箱验证）
- 注册即用：浏览器 https://browser.dataspace.copernicus.eu/ 可检索 Sentinel-2 L2A 影像（本项目 M6 正式批用，现阶段只需账号就绪，无需下载）。
- 许可："Full, Free & Open"，可商用可烘焙（上游档案已核）。

## 3. GEBCO（解锁 M6 水深）

- **直达**：https://www.gebco.net/data_and_products/gridded_bathymetry_data/
- 下载 GEBCO 2025 网格需在门户接受许可（公有领域；具体是表单还是账号以页面为准——M6 正式批会给出精确区域子集下载参数，现阶段先走通注册/许可流程）。

## 4. BIG 印尼（解锁 DEMNAS 8m 高程 + BATNAS 水深 —— 可选增强）

- **直达**：https://tanahair.indonesia.go.id/ （印尼国家地理信息局门户，注册免费）
- 用途：Batam/Bintan 侧 8m 高程替换 GLO-30 的 30m（GLO-30 已可用，此项属锦上添花）；界面为印尼语，注册有邮箱验证。
- **可选**：若嫌繁琐可跳过——不影响 M6 主线。

## 5. OneMap（解锁 M7 新加坡矢量 —— 可后置）

- **直达**：https://www.onemap.gov.sg/docs/ （新加坡官方地图 API，免费注册取 key）
- 用途：M7 布景（岸线/建筑矢量补充）；SODL 许可须按模板署名。M7 开工前完成即可。

## 6. Fab / Epic（解锁 Megascans 免费层 —— M7 植被材质）

- **直达**：https://www.fab.com/ （Epic 账号登录）
- 用途：约 1,500 免费扫描资产 + Megaplants 全免费（热带植被/岩石/滩涂材质，M7 用）；Fab Standard License 全文下载前留意（上游档案 L1 待证项）。

## 完成回报方式

每完成一项说一声即可（如"Sketchfab 好了"）；**第 1 项（Sketchfab+9 件下载落盘）完成即触发 M5 免费船队导入批**（workflow 已改靶待发）；2/3 完成触发 M6 正式批（S2 底图+水深）；4/5/6 按各自里程碑需要触发。
