# M5 采购船队面数审计（C3 闸门）— m5-audit

- 日期：2026-09-29 ｜ 工具：`Sango.Editor.M5AssetAudit`（menu Sango/M5/Audit Purchased Fleet，batchmode `-executeMethod Sango.Editor.M5AssetAudit.Run`）
- 闸门：**hero ≤150,000 tri**（C3）；超标船记录裁决=减面或降级中景，不静默入库。
- 面数为 Unity 导入后实测（全部 MeshFilter × 全部 submesh 索引和，去重网格）；Sketchfab faceCount 仅作对照。
- 包围盒 = 恒等姿态实例化的世界渲染器并集（含 FBX 导入缩放）；偏差>20% 记 finding，编目 LOA 归一化时修正。

| 船 | 角色 | tri | verts | 贴图 | UV 通道 | LOD | 包围盒 (x,y,z m) | 实测水平边 | 预期 LOA | 偏差 | C3 裁决 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fishing-trawler | 中远 | 5,253 | 9,216 | 无（flat/顶点色） | 1 | 0 | (35.3, 14.5, 9.0) | 35.3 | 25 | +41% | 过闸（≤150k） |
| cargo-general | 中景 | 73,448 | 72,180 | Image_0 2048x2048; Image_2 2048x2048; Image_3 2048x2048; Image_5 2048x2048; Image_6 2048x2048; Image_8 2048x2048 | 1 | 0 | (127.1, 39.7, 19.3) | 127.1 | 125 | +2% | 过闸（≤150k） |
| cargo-container | 中景 | 188,711 | 263,610 | Bridge_Base_color_sRGB 2048x2048; Bridge_Normal_DirectX_Raw 2048x2048; Containers_Base_color_sRGB 2048x2048; Containers_Normal_DirectX_Raw 2048x2048; Hull_Base_color_sRGB 2048x2048; Hull_Normal_DirectX_Raw 2048x2048 | 1 | 0 | (62.8, 11.6, 8.9) | 62.8 | 150 | -58% | **超 150k：限中景（不入 hero，不减面本批）** |
| tanker-suezmax | 中景 | 192,789 | 190,804 | 无（flat/顶点色） | 1 | 0 | (20.1, 27.2, 162.3) | 162.3 | 300 | -46% | **超 150k：限中景（不入 hero，不减面本批）** |
| tanker-lng | 中景 | 89,901 | 68,752 | 无（flat/顶点色） | 1 | 0 | (6.6, 8.5, 43.5) | 43.5 | 300 | -85% | 过闸（≤150k） |
| tug-rastar3200 | 中景 | 46,880 | 53,218 | Image_0 2048x2048 | 1 | 0 | (13.5, 23.1, 32.9) | 32.9 | 30 | +10% | 过闸（≤150k） |
| fcb-houbei | hero 候选 | 17,708 | 25,497 | Image_0 512x256; Image_1 512x512; Image_2 512x512; Image_3 512x512; Image_4 1024x512 | 1 | 0 | (303.4, 374.3, 937.8) | 937.8 | 42 | +2133% | 过闸（hero 可用） |
| fcb-pc3 | 中景/剪影 | 14,484 | 21,611 | Image_0 1024x1024; Image_1 256x256; Image_10 16x16; Image_11 16x16; Image_12 64x64; Image_13 16x16 (+8) | 1 | 0 | (3.6, 5.4, 21.5) | 21.5 | 55 | -61% | 过闸（≤150k） |
| quaternius-boat | 远景剪影(CC0) | 172 | 300 | 无（flat/顶点色） | 0 | 0 | (0.4, 0.2, 0.7) | 0.7 | — | — | 过闸（≤150k） |
| quaternius-cruise | 远景剪影(CC0) | 858 | 1,330 | 无（flat/顶点色） | 1 | 0 | (4.0, 6.6, 18.0) | 18.0 | — | — | 过闸（≤150k） |

## 逐船明细

### fishing-trawler (`Assets/Art/Purchased/fishing-trawler/source/Trawler.fbx`)

- tri 5,253 / verts 9,216（去重网格 1 个，submesh 全计）
- 艏向证据：船轴 X（extent 35.3）· −X端 5.41 / +X端 6.98 → 艏 −X → yaw 90°（艏端宽 5.41 / 艉端宽 6.98）
- 渲染器 1 个；UV 通道 1；LODGroup 0 个
- 材质 shader：HDRP/Lit

### cargo-general (`Assets/Art/Purchased/cargo-general/source/cargo_ship.fbx`)

- tri 73,448 / verts 72,180（去重网格 8 个，submesh 全计）
- 艏向证据：船轴 X（extent 127.1）· −X端 16.37 / +X端 19.24 → 艏 −X → yaw 90° ⚠ 端宽差<15%（盒形/双体），自动判定模糊，以人工钉值为准（艏端宽 16.37 / 艉端宽 19.24）
- 渲染器 8 个；UV 通道 1；LODGroup 0 个
- 贴图清单：
  - Image_0 2048x2048
  - Image_2 2048x2048
  - Image_3 2048x2048
  - Image_5 2048x2048
  - Image_6 2048x2048
  - Image_8 2048x2048
- 材质 shader：HDRP/Lit

### cargo-container (`Assets/Art/Purchased/cargo-container/source/Ship.fbx`)

- tri 188,711 / verts 263,610（去重网格 2 个，submesh 全计）
- 艏向证据：船轴 X（extent 62.8）· −X端 8.82 / +X端 8.86 → 艏 −X → yaw 90° ⚠ 端宽差<15%（盒形/双体），自动判定模糊，以人工钉值为准（艏端宽 8.82 / 艉端宽 8.86）
- 渲染器 2 个；UV 通道 1；LODGroup 0 个
- 贴图清单：
  - Bridge_Base_color_sRGB 2048x2048
  - Bridge_Normal_DirectX_Raw 2048x2048
  - Containers_Base_color_sRGB 2048x2048
  - Containers_Normal_DirectX_Raw 2048x2048
  - Hull_Base_color_sRGB 2048x2048
  - Hull_Normal_DirectX_Raw 2048x2048
- 材质 shader：HDRP/Lit

### tanker-suezmax (`Assets/Art/Purchased/tanker-suezmax/source/tanker_ship.fbx`)

- tri 192,789 / verts 190,804（去重网格 47 个，submesh 全计）
- 艏向证据：船轴 Z（extent 162.3）· −Z端 19.63 / +Z端 19.57 → 艏 +Z → yaw 0° ⚠ 端宽差<15%（盒形/双体），自动判定模糊，以人工钉值为准（艏端宽 19.57 / 艉端宽 19.63）
- 渲染器 47 个；UV 通道 1；LODGroup 0 个
- 材质 shader：HDRP/Lit

### tanker-lng (`Assets/Art/Purchased/tanker-lng/source/lng_ship.fbx`)

- tri 89,901 / verts 68,752（去重网格 20 个，submesh 全计）
- 艏向证据：船轴 Z（extent 43.5）· −Z端 5.80 / +Z端 5.25 → 艏 +Z → yaw 0° ⚠ 端宽差<15%（盒形/双体），自动判定模糊，以人工钉值为准（艏端宽 5.25 / 艉端宽 5.80）
- 渲染器 20 个；UV 通道 1；LODGroup 0 个
- 材质 shader：HDRP/Lit

### tug-rastar3200 (`Assets/Art/Purchased/tug-rastar3200/source/rastar_3200_tugboat.fbx`)

- tri 46,880 / verts 53,218（去重网格 13 个，submesh 全计）
- 艏向证据：船轴 Z（extent 32.9）· −Z端 11.73 / +Z端 11.69 → 艏 +Z → yaw 0° ⚠ 端宽差<15%（盒形/双体），自动判定模糊，以人工钉值为准（艏端宽 11.69 / 艉端宽 11.73）
- 渲染器 13 个；UV 通道 1；LODGroup 0 个
- 贴图清单：
  - Image_0 2048x2048
- 材质 shader：HDRP/Lit

### fcb-houbei (`Assets/Art/Purchased/fcb-houbei/source/type_22_missile_boat.fbx`)

- tri 17,708 / verts 25,497（去重网格 34 个，submesh 全计）
- 艏向证据：船轴 Z（extent 936.1）· −Z端 207.96 / +Z端 275.71 → 艏 −Z → yaw 180°（艏端宽 207.96 / 艉端宽 275.71）
- 渲染器 34 个；UV 通道 1；LODGroup 0 个
- 贴图清单：
  - Image_0 512x256
  - Image_1 512x512
  - Image_2 512x512
  - Image_3 512x512
  - Image_4 1024x512
- 材质 shader：HDRP/Lit

### fcb-pc3 (`Assets/Art/Purchased/fcb-pc3/source/lowpoly_uss_hurricane_pc-3.fbx`)

- tri 14,484 / verts 21,611（去重网格 39 个，submesh 全计）
- 艏向证据：船轴 Z（extent 21.2）· −Z端 2.47 / +Z端 2.88 → 艏 −Z → yaw 180° ⚠ 端宽差<15%（盒形/双体），自动判定模糊，以人工钉值为准（艏端宽 2.47 / 艉端宽 2.88）
- 渲染器 39 个；UV 通道 1；LODGroup 0 个
- 贴图清单：
  - Image_0 1024x1024
  - Image_1 256x256
  - Image_10 16x16
  - Image_11 16x16
  - Image_12 64x64
  - Image_13 16x16
  - Image_2 16x16
  - Image_3 128x128
  - Image_4 256x256
  - Image_5 128x128
  - Image_6 64x64
  - Image_7 128x128
  - Image_8 256x256
  - Image_9 128x128
- 材质 shader：HDRP/Lit

### quaternius-boat (`Assets/Art/Purchased/Quaternius/source/Boat.fbx`)

- tri 172 / verts 300（去重网格 1 个，submesh 全计）
- 艏向证据：船轴 Z（extent 0.7）· −Z端 0.26 / +Z端 0.06 → 艏 +Z → yaw 0°（艏端宽 0.06 / 艉端宽 0.26）
- 渲染器 1 个；UV 通道 0；LODGroup 0 个
- 材质 shader：HDRP/Lit

### quaternius-cruise (`Assets/Art/Purchased/Quaternius/source/CruiseShip.fbx`)

- tri 858 / verts 1,330（去重网格 1 个，submesh 全计）
- 艏向证据：船轴 Z（extent 18.0）· −Z端 3.46 / +Z端 3.08 → 艏 +Z → yaw 0° ⚠ 端宽差<15%（盒形/双体），自动判定模糊，以人工钉值为准（艏端宽 3.08 / 艉端宽 3.46）
- 渲染器 1 个；UV 通道 1；LODGroup 0 个
- 材质 shader：HDRP/Lit


## 附：seed-42 岛群实测（锚地/航线清障数据）

```
seed 42，5 岛，sizeRange 80-240 m，cluster r=260 m，cluster center (0,0,180)
岛 Island-43: local (211.2, 3.5)  world (211.2, 183.5)  R≈48.9 m  可视岸线≈39.1 m
岛 Island-44: local (142.2, -197.4)  world (142.2, -17.4)  R≈66.8 m  可视岸线≈53.5 m
岛 Island-45: local (129.0, -147.1)  world (129.0, 32.9)  R≈98.1 m  可视岸线≈78.5 m
岛 Island-46: local (2.1, 216.9)  world (2.1, 396.9)  R≈102.9 m  可视岸线≈82.4 m
岛 Island-47: local (-30.9, -128.4)  world (-30.9, 51.6)  R≈76.5 m  可视岸线≈61.2 m
```

## 人工裁决与批次决定（2026-09-29，导入工程师记录；上方表格为工具实测）

### C3 逐船裁决（hero ≤150k tri）

| 船 | tri 实测 | 裁决 | 处置 |
|---|---|---|---|
| fcb-houbei | 17,708 | **hero 过闸** | 入编目 `FcbHoubei`，换白壳绿装+轮胎护舷，替换 M1 演示主角（G 自航语义不变，相机跟随/雷达/矢量箭头/检测框/自主面板全部换目标） |
| fcb-pc3 | 14,484 | 过闸（中景/剪影） | 入编目 `FcbPc3`，锚地槽位 3 + 远景副选 |
| fishing-trawler | 5,253 | 过闸（中远） | 入编目 `FishingTrawler`；M1 场景静态泊位 (-16,-28) 近景尺度参照 |
| cargo-general | 73,448 | 过闸（中景） | 入编目 `CargoGeneral`，锚地槽位 4 |
| tanker-lng | 89,901 | 过闸（中景） | 入编目 `TankerLng`，锚地槽位 6（东远水） |
| tug-rastar3200 | 46,880 | 过闸（中景） | 入编目 `Tug`，锚地槽位 1 |
| cargo-container | 188,711 | **超 150k → 限中景**（不减面本批） | 入编目 `CargoContainer`，仅锚地布景（槽位 5）；不作 hero；减面留 follow-up |
| tanker-suezmax | 192,789 | **超 150k → 限中景**（不减面本批） | 入编目 `Tanker`，仅锚地布景（槽位 7）；不作 hero；减面留 follow-up |

全队合计静态面数（8 船全摆）≈ 729k tri；默认密度 5 槽 ≈ 328k tri。无 LOD（全部 0 层，采购件不带）——中景布景可接受，hero FCB 17.7k 轻量。UV 全部 1 通道。

### 尺度核验 findings（>20% 偏差，编目归一化修正）

链路（glTF→Blender→FBX→Unity）单位每船不一，实测水平边 vs 预期 LOA：trawler +41%、container −58%、tanker −46%、lng −85%、pc3 −61%、**houbei +2133%**（cm 级建模未归一）。cargo-general +2%、tug +10% 在带内。全部经编目 LOA 归一化烘焙（prefab 根统一缩放）修正，EditMode 测试 ±10% 钉死（M5FleetCatalogTests）。作者 desc 尺度（Suez-Max 322 m / LNG 305 m）超出任务带 200-300 m 上限 → 按带内 300 m 归一（finding 记录，不改实船尺度叙事）。

### 艏向钉值（BowYawDeg，4 向端宽实测证据）

盒形船体（箱船/油轮/拖轮）端宽近平局（差 <15%），自动判定模糊——按实测方向钉值并在 k_Specs 注释标 ⚠，GUI 目检翻案时改字面量+测试同步：

| 档位 | yaw | 端宽证据（艏/艉） | 置信 |
|---|---|---|---|
| FishingTrawler | 90° | 5.41/6.98（−X 艏） | 中（22% 差） |
| CargoGeneral | 90° | 16.37/19.24（−X 艏） | ⚠ 低（15%） |
| CargoContainer | 90° | 8.82/8.86（−X 艏） | ⚠ 极低（近平局） |
| Tanker | 0° | 19.57/19.63（+Z 艏） | ⚠ 极低 |
| TankerLng | 0° | 5.25/5.80（+Z 艏） | ⚠ 低 |
| Tug | 0° | 11.69/11.73（+Z 艏） | ⚠ 极低（ASD 拖轮艉宽合理） |
| FcbHoubei | 180° | 207.96/275.71（−Z 艏） | **高**（25% 差） |
| FcbPc3 | 180° | 2.47/2.88（−Z 艏） | ⚠ 低 |

### 材质转换记录（任务项 3）

- 全部出货材质（Standard/Built-in）逐槽位重建 **HDRP/Lit** + base color 回接（37/55 材质带 _BaseColorMap；其余 flat tint 承接 FBX 漫反射色——tanker/LNG 的 GLB 本就无贴图）。粉紫（shader 丢失）由 `M5FleetCatalogTests.Prefab_AllRendererMaterials_AreHdrpLit_NotPink` 全档钉死。
- 已知简化：法线（DirectX 绿通道约定差异）、金属度/粗糙度 Mask（需通道烘焙）本批不接——中景布景可接受，记 follow-up。
- Houbei 占位换装：白壳 (0.93,0.94,0.92) + 绿装 (0.13,0.32,0.20) flat 调色板（规则：渲染器沿船长跨度 ≥45% LOA → 白，其余 → 绿）+ 程序化 torus 轮胎护舷两舷各 6 环（R 0.55/r 0.22 m，黑 flat）。无贴图工序、无 AI 生成（维持调研口径）。

### 吃水估值口径（draftFraction = 吃水/总高）

逐船主甲板线顶点分析未做（M2-A Kenney 档做过，本批 8 船代价过高）；按实船典型吃水 ÷ 审计实测归一化总高折算：trawler 2.6/10.3=0.25 · cargo 7.5/37.5=0.20 · container 8.3/27.7=0.30 · tanker 14/50=0.28 · lng 11.7/58.6=0.20 · tug 5.4/22.5=0.24 · houbei 1.7/16.8=0.10 · pc3 2.1/13.8=0.15（米）。观感定值，实测水线待 GUI 验收回填。

### FCB demo 航线与锚地槽位（离线验证，AnchorageSlotsTests 守不变量）

- 航线：(30,-12) 泊位 → (52,-36) → (72,-64) → (30,-78) → (-6,-50)，42×12.6 m 船体矩形 4 角逐米采样 vs 全部岛岸线盘（0.8R）最差裕量 **6.0 m**（旧 M2-C 航线为 12 m 船核过，42 m 船在 (56,-8) 一带侵入岛 C 岸线盘 17 m，故改线南下开阔水域）。巡航 8 m/s（≈16 kn 快巡档）/ 25°/s / 到达半径 12 m。
- 锚地槽位（按成本升序）：Tug(144,-140) → Trawler(60,-176) → Pc3(144,-248) → CargoGeneral(264,-68) → CargoContainer(312,-260) → TankerLng(420,200) → Tanker(160,600)。约束：岛岸线 ≥ 半对角+12 · 航线 ≥50 m · 静态泊位 ≥70 m · 船间 ≥ 半对角和+60。首版 LNG(380,64) 与 CargoGeneral 间距 175.7 m 违规（离线搜索分组漏查跨组对，AnchorageSlotsTests 拦下）→ 移 (420,200)。
- 密度滑条进 Simulation 面板 M5 ANCHORAGE 段（live 重建，M4-A 模式），默认 5。
