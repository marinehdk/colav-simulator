# M6 正式批·数据段 —— 新加坡海峡地形 + S2 底图正式管线（2026-09-29）

脚本：`tools/terrain/m6_pipeline.sh`（幂等，无下载；源=spike 落盘的 GLO-30 六 tile + GEBCO 子集 + S2 UG TCI，只读）。
产物：`tmp/m6-data/`（manifest.json + tiles/ 29 组 + basemap/ 29 组 + dem/ 中间件）——tmp 不入库，判据图与本 notes 入库。
规格定案：C2 双档裁决（`docs/research/2026-09-29-m6-terrain-spike/notes.md` §C2）。

## 规格表（固定，与脚本顶部常量、manifest.json 一致）

| 项 | 近景带 near | 远景带 far |
|---|---|---|
| 带域（UTM 48N, 中心±） | 24×24 km（±12 km） | 60×60 km（±30 km） |
| tile 网格 | 2×2 | 5×5 |
| 每 tile 高度图 | 2049²（2^11+1） | 513²（2^9+1） |
| m/px（-tr 精确值） | 12000/2048 = **5.859375** | 12000/512 = **23.4375** |
| 整带光栅（先 warp 后 -srcwin 切） | 4097² | 2561² |
| 每 tile S2 底图 JPG | 2048²（quality 90） | 512²（quality 90） |
| 高度图 u16 scale（带内全域，带内共用） | min=**-191.5692**, max=**188.4488** m | min=**-191.7258**, max=**188.3606** m |

- 中心 (103.80E, 1.28N) → UTM48N **(366493.325, 141509.930)**（脚本 gdaltransform 实算）= Unity 世界原点（浮点原点约定）。
- tile 命名 `{tier}_r{row}c{col}_{px}`，**row 0 = 最北行**（与图像行序一致）；`utm_bounds=[xmin,ymin,xmax,ymax]`。
- 采样格（vertex-grid）约定：带光栅 origin=逻辑域西北角，宽=格数+1 个像元（东/南各 1 共享 px）；相邻 tile 共享 1 px 边，由同源 `-srcwin` 直拷保证零缝隙（V4 checksum 实证 44/44）。
- RAW 约定（沿用 spike 实测）：ENVI 裸 u16、**小端**（hdr `byte order = 0` + 数据探针双证）、**行序北上**、单带 BSQ。Unity Import Raw 选小端；terrain size=12000 m（2049 采样跨 2048 格）。
- u16↔米换算（每带一对）：`elev_m = u16/65535*(max-min)+min`（near: span 380.0180 m；far: span 380.0864 m）。

## 陆海合并（替代 spike 海面钳平）

- 陆 = GLO-30 ≥0.5 m 用 GLO（全域窗 103.40–104.40E/1.45S–1.45N @30 m，与 spike 同窗同格网）；海 = GEBCO 15″ 双线性上采样到同格网；海岸 **2 km feather**：`w=clip(dist_land/2000m,0,1)`，`merged=(1-w)*GLO+w*GEBCO`（scipy 距离场）。全域 merged min=**-191.736** / max=**303.381** m，陆像元 21.11%。
- **不做钳平**：海面下即真实水深（负值）。spike 已知的重采样海面残差渗入做二次清理：合并源 30 m 海陆掩膜 nearest 到带格网后，陆 `max(v,0)`、海 `min(v,0)`——海不高于 0、陆不低于 0；feather 主体在海上（负值）不受影响（`04_feather_profile.png` 判读：过渡带宽 ~1–2 km，陆内贴合 GLO、海内贴合 GEBCO）。
- 分带重采样：近景 30→5.86 m bilinear（5.1× 上采样），远景 30→23.4 m average（防混叠）；掩膜一律 nearest。

## S2 底图

- 仅 UG 单景 `S2B_48NUG_20260320_0_L2A`（10 m sRGB TCI）；60 km 窗边界余量 L/R/B/T = **36493/13307/21270/28530 m ≥10 km**（脚本断言）。
- 近景 tile bilinear 上采样、远景 tile average 下采样 → JPG quality 90 + `.wld` worldfile；sRGB 原色不变换。
- **VG 两景（48NVG 2026-03-20 云 12.5%、2026-04-23 云 8.2%）不入管线**：云量偏高，且 VG 覆盖（x≥399960）不含近景带，只可作远景东侧将来扩展（manifest s2.note 已记）。

## 核验输出摘录（VERIFY 全过，EXIT=0；完整输出见 `tmp/m6-data-run.log`）

```
-- [V1] near raw/hdr/tif/jpg = 4/4/4/4, far = 25/25/25/25, basemap .wld = 29 OK
-- [V2] RAW↔GTiff checksum: 29/29 一致 OK
-- [V3] 字节序: near hdr byte order=0, pixel(0,0)=36965 ↔ bytes 6590 → LITTLE-endian OK
        far  hdr byte order=0, pixel(0,0)=33058 ↔ bytes 2281 → LITTLE-endian OK
-- [V4] 共享边 44 条（near 4 + far 40）checksum 全等 OK（缝隙零差异）
-- [V5] 29 tiles + 2 band: size/EPSG:32648/res OK（near 5.859375 / far 23.4375 m/px）
-- [V6] 29/29 tile: S2 jpg 与 DEM 逻辑域（原点/12km Extent/分辨率）一致（tol 1e-4 m）OK
-- [V7] manifest OK: near=4 far=25, near elev [-191.569, 188.449], far elev [-191.726, 188.361]
-- [V8] land mean RGB=117/119/103（绿灰，城市+植被）; deep-sea mean RGB=80/106/110（蓝绿浊水, b>r 断言过）
        云斑判据（陆面高亮低饱和占比）= 11.835%  [WARN]>3%  → 见下"已知限制"
```

## 判据图（本目录）

| 文件 | 内容 | 判读（2026-09-29 批末人工 + 视觉模型） |
|---|---|---|
| `01_near_hillshade.png` | 近景带 4097² hillshade（-z 3） | 陆地起伏优秀：Bukit Timah 山群、Sentosa/南部群岛丘脊、填海平台平整可辨；海面低频起伏=GEBCO 水深非伪影 |
| `02_near_s2_hillshade_overlay.png` | 近景带 S2×hillshade 叠加 | 陆绿灰/海蓝绿，主航道清晰；**NE 新加坡陆面+北缘云斑 ~10–15% 陆面**（见限制） |
| `03_far_color_relief.png` | 远景带彩色浮雕（含水深色带） | 地理格局成立：Johor 北 / Singapore 中 / Batam-Bintan 南 / 主航道深水斜贯；海岸 feather 光晕平滑，无人工直缝/数据洞 |
| `04_feather_profile.png` | 陆海合并剖面（y=center，±15 km） | 陆段贴合 GLO、海段贴合 GEBCO、过渡 ~1–2 km 平滑无跳变 |

## manifest.json 契约（Unity 段直接消费）

字段名即契约（`tmp/m6-data/manifest.json`）：
`epsg`=32648（int）；`center_lonlat`/`center_utm`（Unity 世界原点）；`feather_m`；`near`/`far`：`extent_utm`(4 元) `tile_px` `tile_size_m`(=12000) `grid` `m_per_px` `basemap_px`(底图 2048/512) `elev_min/max`(u16 scale) `tiles[]`：`{name, utm_bounds, path_raw, path_jpg}`——**path 一律仓库根相对**（如 `tmp/m6-data/tiles/near_r0c0_2049.raw`；消费方从仓库根解析，V7 按此断言存在性）；`s2`：`{scene,date,res_m,srgb,source,note}`；`generated_by`。
注意：`utm_bounds`/`extent_utm` 为**逻辑域**（12 km tile / 24–60 km 带）；RAW 光栅比逻辑域多东/南各 1 共享 px（Unity 按 terrain size=12000 导入即可）。

## 已知限制 / followUps

1. **近景带陆面云斑（如实上报）**：UG 景目录云 11.1%（CDSE 目录值），读图证实集中在 NE 新加坡陆面+北缘，约 10–15% 陆面受影响；海面（玩法主区）基本晴好。补丁方案（未执行，勿自行改用 VG——VG 不覆盖近景带且云量更高）：
   a) **多时相 cloud-fill**：UG 同 tile 其他日期（`tmp/cog-dates-UG-2026.txt` 有全表，如 2026-01 系列 S2B/S2C）逐像元替换云区；
   b) **换更低云量对**：2026-08-22 S2C 对（VG 2.8%/UG 13.1%）需 CDSE 登录下载；
   c) 短期遮丑：Unity 段近景带陆地用 splat/细节层压暗（云在陆不在海，视觉权重低）。
2. 云斑数值判据（高亮低饱和）会把新加坡 CBD 高亮屋面/混凝土计入（11.8% 里含城市亮面），不能单独当云量用；以读图为准。
3. GEBCO 15″（≈460 m）上采样到 5.86 m 后海部呈平滑块状（近景 hillshade 右下可见）——水深细节天花板，非接缝伪影（V4 缝隙 checksum 已证零差异）；升级路径=BATNAS/DEMNAS 印尼侧（需 BIG 账号，spike notes 已列）。
4. 深海均值 80/106/110 偏青绿：赤道浑浊浅海真实水色（b>r 断言过），若 Unity 水面着色希望更"深蓝"应在渲染层调，不是数据错。
5. far 带 u16 scale 与 near 不同（带内各自 min/max）——跨带灰度不可直接比大小，换算回米数后可比（公式见上）。
6. Unity 端 RAW 导入（小端/翻转/terrainHeight=380.018|380.086 全量程或按带裁）未实测——M6 Unity 批首项验证。
7. 重跑覆盖重生成（幂等已证：调试期连跑 ≥6 次含 2 次全绿 EXIT=0）；`tmp/m6-spike-data/` 全程只读。

## 数据与许可（登记表 `sango/Docs/asset-registry.md` 同批补行）

- GEBCO 栅格子集：公有领域（gebco.net），引用 `GEBCO Bathymetric Compilation Group 2026 (2026). The GEBCO_2026 Grid... DOI: 10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa`；子集经 download.gebco.net 工具落盘 2026-09-29（当期发布 GEBCO_2026；文件未内嵌版本号）。
- Sentinel-2 L2A TCI（element84 sentinel-cogs，AWS 开放数据）：Copernicus Sentinel 数据免费/全量/开放（EU Reg. 1159/2013 & 2019/1154）；署名 `Contains modified Copernicus Sentinel data 2026, processed by ESA`。
- GLO-30：spike 已登记（© Copernicus DEM / ESA）。
