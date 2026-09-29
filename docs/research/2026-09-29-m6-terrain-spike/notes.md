# M6 地形 spike（2026-09-29）— 新加坡海峡 GLO-30 管线

脚本：`tools/terrain/spike1.sh`（幂等，重跑覆盖不报错——本次已连跑 3 遍验证，第 3 遍 EXIT=0）。
判据问题（00-REPORT §7）：免费数据能否做出"岛屿有起伏"的海峡地形 + 裁决 C2（2049² vs 513² 分块口径，定义见 `docs/research/2026-09-24-scene-ship-fidelity/verify.md:42`、`00-REPORT.md:183`）。

## 结论（一句话）

**免费 GLO-30 足以做出岛屿有起伏的海峡地形**——全域窗内岛屿高程 0–303 m（近景窗 0–106.8 m，含花柏山一类丘陵），hillshade/彩色浮雕判据图（本目录 6 张 PNG）逐像素核对无误；2049/513 两档 RAW 均已产出且与 GTiff checksum 一致。

## 数据与许可

- Copernicus GLO-30（AWS 公开镜像，匿名）：`https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{T}_DEM/Copernicus_DSM_COG_10_{T}_DEM.tif`
- 6 tile：N01/N00/S01 × E103/E104，共 115.6 MB（仅落 `tmp/m6-spike-data/tiles/`，不入库）
- 许可：Copernicus "Full, Free & Open"，署名 © Copernicus DEM / ESA（已登记 `sango/Docs/asset-registry.md`）
- 下载实测：S3 匿名可达但本机带宽仅 ~25–45 KB/s，6 tile 约耗时 35 min；脚本对已存在且 gdalinfo 可解析的 tile 跳过重下（幂等关键）。

## 管线（全部在脚本内，可重跑）

1. curl -fL --retry 3 下载 6 tile（存在且可解析则跳过）
2. `gdalwarp` 合并+裁剪 `103.40–104.40E, 1.45S–1.45N`（`-te_srs EPSG:4326`）→ **EPSG:32648**（UTM 48N）30 m float32
3. `gdal_calc` 海面钳平：`where(A>=0.5, A, 0)`（<0.5 m → 0）
4. 近景窗：中心 (103.80E, 1.28N) → UTM (366493.3, 141509.9)，±6000 m 方盒 = 12×12 km，30 m 原生 **400×400 px**
5. `gdalwarp -ts` 双档重采样（2049 bilinear 上采样 / 513 average 下采样）→ `gdal_translate -ot UInt16 -scale 0 106.757 0 65535`（**两档共用同一 scale**，保证灰度可比；max 取原生 400×400 窗统计，故 2049 档 u16 max=65429 属预期）→ GTiff + ENVI RAW 双副本
6. `gdaldem` hillshade + color-relief 判据 PNG（本目录）
7. 自验：字节序探针、RAW↔GTiff checksum、文件大小、gdalinfo 规格

## 实测规格（gdalinfo，本次 run3 输出）

| 产物 | 规格 |
|---|---|
| `straits_merged.tif` | 3711×10689 px, 30 m/px, EPSG:32648, bbox lon 103.3995–104.4001 / lat −1.4505–1.4505, **min −37.0 m, max 303.4 m**（min 即 GLO-30 海面插值噪声幅值，钳平依据） |
| `straits_clamped.tif` | 同上几何；海面 0 |
| `near_window_f32.tif` | 400×400 px @30 m, min 0, max 106.757 m |
| `near_2049_u16.tif/.raw` | 2049×2049, 5.8565 m/px, UInt16 |
| `near_513_u16.tif/.raw` | 513×513, 23.3918 m/px, UInt16 |

近景窗范围（UTM 32648）：360493.3 135509.9 372493.3 147509.9（≈103.738–103.862E, 1.226–1.334N）。

## 海面处理边界（重要）

本 spike 用 `<0.5 m → 0` 钳平得**平坦海面**；**真实 bathymetry 留 GEBCO 正式批**（GEBCO_2025 陆海合并 + 海岸带 feather，见 dive_04 方案）。已知小瑕疵：钳平在原生 30 m 上做，重采样后亚 0.5 m 海面值会轻微回渗（bilinear(0, 0.6)=0.3 m → u16 ≈ 184，约 0.3 m 灰阶），观感可忽略；正式批应在重采样后再钳一次。

## px/m 表（C2 裁决材料）

| 档 | px | m/px | RAW 字节 | R16 显存(估) | 12×12 km/tile 数·全带(60×60 km) |
|---|---|---|---|---|---|
| near_2049 | 2049²（2^11+1，Unity 合法） | **5.86** | 8,396,802 B = 8.0 MiB | 8.0 MiB/tile | 25 tile ≈ **200 MiB** |
| near_513 | 513²（2^9+1，Unity 合法） | **23.39** | 526,338 B = 0.5 MiB | 0.5 MiB/tile | 25 tile ≈ **12.5 MiB** |

裁决输入（数据侧事实，不做决定）：

1. **GLO-30 原生 30 m 是细节天花板**：12×12 km 窗原生只有 400×400 px。2049 档 = 5.1× 上采样（bilinear 平滑，不新增真实细节，好处是高度图格网细、海岸线锯齿小、后续可融合更高分辨率源）；513 档 23.4 m/px 已接近原生密度，几乎无信息损失。
2. 显存/磁盘差 **16×**（8.0 vs 0.5 MiB/tile）。
3. 调研数字澄清：00-REPORT.md:84 写"近景带 ≈20×20 km 按 2049²（≈5.9 m/格）"内部矛盾（20 km/2049=9.76 m/格）；5.9 m/格 ⇒ 12×12 km/tile（本 spike 口径）。verify.md:42 的"≈12 km²/tile"应为"12×12 km/tile"（否则 60×60 km 需 300 tile，与"数十 tile"矛盾）。
4. 对比图：`05_near2049_hillshade_1024px.png` vs `06_near513_hillshade_1024px.png`（同画布同光源同夸张，513 档格感明显）。

## RAW 约定（M6 正式批 Unity 导入直用）

- **字节序：小端（little-endian）**——GDAL 3.13.0 ENVI 驱动本机实测 `.hdr` 写 `byte order = 0`（ENVI 规范 0=小端），且数据字节探针复核（pixel(0,0)=5528=0x1598 ↔ 首字节 `98 15`）。Unity Import Raw 字节序选小端（Windows/Mac 档）。
- **行序：北上（row 0 = 最北）**，GDAL GeoTIFF/ENVI 一律 north-up。Unity Import Raw 若导入后南北颠倒 → 勾选 Flip Vertically（本 spike 未跑 Unity，未实测 Unity 端表现）。
- **布局**：单带 UInt16 BSQ（行主序），无头裸二进制；尺寸见上表。`data type = 12`（ENVI 的 UInt16 码）。
- **值域换算**：u16 = elev_m / 106.757 × 65535（线性，两档同参）。Unity 端还原真实米数：heightmap 0–1 × terrainHeight，terrainHeight ≈ 106.757（或按观感加夸张系数，需同步记档）。

## EPSG 勘误（记录在案）

dive_04.md:12 与 00-REPORT.md:84 写"UTM 48N（EPSG:32748）"——**32748 是 UTM 48S（南半球），笔误**；北纬新加坡正确代号 **EPSG:32648**（UTM 48N，中央经线 105E）。本管线用 32648，后续 M6 全部沿用。

## 判据图清单（本目录）

| 文件 | 内容 |
|---|---|
| 01_full_hillshade.png | 全域 1200×3456 hillshade（-z 2） |
| 02_full_color_relief.png | 全域彩色浮雕（海蓝-绿-棕） |
| 03_near_hillshade.png | 近景窗 2049² hillshade（-z 3） |
| 04_near_color_relief.png | 近景窗彩色浮雕 |
| 05/06_near*_hillshade_1024px.png | 2049 vs 513 同画布对比 |

像素级验证：elev 0 → (18,60,105) 海蓝、elev 42.88 m → (82,132,61)、elev 6.05 m → (200,214,217) 浅滩淡蓝，均与色表插值逐点吻合。

## 已知限制 / followUps

- S3 下载慢（~35 min/6 tile）；正式批建议保留"存在即跳过"幂等策略或换镜像（如 Terrascope/PDGE 官方发布）。
- bathymetry 未做（GEBCO 正式批）；海面为 0 m 平面。
- Unity 端 RAW 导入（字节序/翻转/terrainHeight）未实测——M6 正式批首项验证。
- tmp/ 实际**不在** .gitignore（本 spike 靠显式路径 add 保障入库范围；git status 有 tmp 噪音，主 agent 可决定是否补 ignore 规则）。
- `verify.md` "12 km²" 与 `00-REPORT` "20×20 km/5.9 m/格"两处调研内部矛盾建议回写勘误（C2 裁决时一并处理）。

## C2 分块口径裁决（主 agent，2026-09-29）

读图判据（05/06/02 三张）+ 实测规格，裁决 **双档并存**：
- **近景带**（主航道+主岛，约 20×20km）＝ **2049²/tile（≈5.86 m/px）**：起伏细节丰富、无量化伪影，且与 S2 底图（10m）细节档匹配——dive_04 的质量判断在近景正确。
- **远景带** ＝ **513²（≈23.4 m/px）**：轻度变粗但小岛完整、主体山脊可辨——dive_07 的成本判断在远景正确。
- 内存口径：近景 tile 单块 u16 高度图 ≈8.4MB + splat，Mac 只载当前 tile（既定红线），全量驻留 a4000。
- 该裁决消解 verify.md C2（口径分歧），回写本档案即为定案。

## 观感判据记录（主 agent 读图，2026-09-29）

- 2049 近景：岛屿轮廓清晰、丘陵/山脊/谷地纹理丰富、无块状伪影——"岛屿有起伏"判据**成立**。
- 513 近景同窗：轻度粗糙化、细碎坡面纹理丢失、小岛无抹平——远景带可用。
- 全域彩色浮雕：新加坡南岸+岛群+主航道格局可辨，陆海对比清晰——"一眼海峡"底座判据**初步成立**（辨识度最终靠 M7 人造密度布景）。

## 后续（M6 正式批）

1. Unity Terrain 导入：RAW u16 + 记录的字节序/翻转约定；近景带按 2049/tile 分块流送（Additive scene）。
2. GEBCO 水深拼接（海面下地形，水色分块用）——等 GEBCO 通道（免注册直下待验证）或账号。
3. S2 L2A 底图（Terrain Lit 首层 base layer 机制）+ OSM landcover splat——等 Copernicus 账号。
4. DEMNAS 8m 印尼侧高程替换 GLO-30——等 BIG 账号（可选增强，30m 已可用）。
