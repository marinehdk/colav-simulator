# M5 采购船队面数审计（C3 闸门）— m5-audit

- 日期：2026-09-29 ｜ 工具：`Sango.Editor.M5AssetAudit`（menu Sango/M5/Audit Purchased Fleet，batchmode `-executeMethod Sango.Editor.M5AssetAudit.Run`）
- 闸门：**hero ≤150,000 tri**（C3）；超标船记录裁决=减面或降级中景，不静默入库。
- 面数为 Unity 导入后实测（全部 MeshFilter × 全部 submesh 索引和，去重网格）；Sketchfab faceCount 仅作对照。
- 包围盒 = 恒等姿态实例化的世界渲染器并集（含 FBX 导入缩放）；偏差>20% 记 finding，编目 LOA 归一化时修正。
- 中心 = 同一包围盒 center（烘焙归属核验：归一化补偿烘在子节点时，源 FBX 中心即模型原始偏移；prefab 侧落位契约由 M5FleetPlacementPoseTests 钉死）。

| 船 | 角色 | tri | verts | 贴图 | UV 通道 | LOD | 包围盒 (x,y,z m) | 中心 (x,y,z m) | 实测水平边 | 预期 LOA | 偏差 | C3 裁决 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fishing-trawler | 中远 | 5,253 | 9,216 | 无（flat/顶点色） | 1 | 0 | (35.3, 14.5, 9.0) | (3.8, 4.7, 0.0) | 35.3 | 25 | +41% | 过闸（≤150k） |
| cargo-general | 中景 | 73,448 | 72,180 | Image_0 2048x2048; Image_2 2048x2048; Image_3 2048x2048; Image_5 2048x2048; Image_6 2048x2048; Image_8 2048x2048 | 1 | 0 | (127.1, 39.7, 19.3) | (-3.1, 53.5, 13.5) | 127.1 | 125 | +2% | 过闸（≤150k） |
| cargo-container | 中景 | 188,711 | 263,610 | Bridge_Base_color_sRGB 2048x2048; Bridge_Normal_DirectX_Raw 2048x2048; Containers_Base_color_sRGB 2048x2048; Containers_Normal_DirectX_Raw 2048x2048; Hull_Base_color_sRGB 2048x2048; Hull_Normal_DirectX_Raw 2048x2048 | 1 | 0 | (62.8, 11.6, 8.9) | (-8.5, 5.8, 0.0) | 62.8 | 150 | -58% | **超 150k：限中景（不入 hero，不减面本批）** |
| tanker-suezmax | 中景 | 192,789 | 190,804 | 无（flat/顶点色） | 1 | 0 | (20.1, 27.2, 162.3) | (0.0, 8.5, 23.5) | 162.3 | 300 | -46% | **超 150k：限中景（不入 hero，不减面本批）** |
| tanker-lng | 中景 | 89,901 | 68,752 | 无（flat/顶点色） | 1 | 0 | (6.6, 8.5, 43.5) | (0.0, 2.2, 6.3) | 43.5 | 300 | -85% | 过闸（≤150k） |
| tug-rastar3200 | 中景 | 46,880 | 53,218 | Image_0 2048x2048 | 1 | 0 | (13.5, 23.1, 32.9) | (0.0, 6.2, -0.9) | 32.9 | 30 | +10% | 过闸（≤150k） |
| fcb-houbei | hero 候选 | 17,708 | 25,497 | Image_0 512x256; Image_1 512x512; Image_2 512x512; Image_3 512x512; Image_4 1024x512 | 1 | 0 | (303.4, 374.3, 937.8) | (-9.6, 10.5, -0.1) | 937.8 | 42 | +2133% | 过闸（hero 可用） |
| fcb-pc3 | 中景/剪影 | 14,484 | 21,611 | Image_0 1024x1024; Image_1 256x256; Image_10 16x16; Image_11 16x16; Image_12 64x64; Image_13 16x16 (+8) | 1 | 0 | (3.6, 5.4, 21.5) | (-0.1, 1.9, 3.0) | 21.5 | 55 | -61% | 过闸（≤150k） |
| quaternius-boat | 远景剪影(CC0) | 172 | 300 | 无（flat/顶点色） | 0 | 0 | (0.4, 0.2, 0.7) | (0.0, 0.1, 0.0) | 0.7 | — | — | 过闸（≤150k） |
| quaternius-cruise | 远景剪影(CC0) | 858 | 1,330 | 无（flat/顶点色） | 1 | 0 | (4.0, 6.6, 18.0) | (0.0, 3.3, 0.2) | 18.0 | — | — | 过闸（≤150k） |

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
