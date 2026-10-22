# Qingdao 影像源参数化（P1-B）——ArcGIS 默认 + 天地图 img_w 切换式接入与部署说明

- 依据：`docs/research/2026-10-19-qingdao-terrain-upgrade-plan.md` §2 P1-B（第四批裁决版，仅免费/开源路线）；
  支撑档 `docs/research/2026-10-19-qingdao-imagery-waterline-rendering.md` §2.4。
- 落地：`sango/Assets/Scripts/Runtime/QingdaoStaticScene.cs`（`ApplyImagerySource` / `SwitchImagery` /
  `ProbeImagery` / `ResolveImagerySource` / `TiandituBaseUrl` / `TiandituTileUrl` / `ArcgisTileUrl`）。
- 测试：`sango/Assets/Scripts/Tests/EditMode/QingdaoImagerySourceTests.cs`（env 解析、token 通道、
  双源 KVP 请求形态、瓦片坐标数学、极点钳制，共 6 例）。

## 机制

| 项 | 内容 |
|---|---|
| `TWIN_QINGDAO_IMAGERY` | `arcgis` \| `tianditu` \| `ion`；**不设/未识别值 = ArcGIS World_Imagery（2026-10-21 起默认，原默认 ion 已废）** |
| `TWIN_QINGDAO_TIANDITU_TOKEN` | 天地图 key；`tianditu` 模式下为空/空白 → 回落 ArcGIS 并告警 |

- **默认为何翻转为 ArcGIS（2026-10-21 六腿实测，a4000）**：ion asset 2 真身=Bing，瓦片 CDN
  `t2.virtualearth.net` **直连与 clash 代理双腿 000（连接失败）**，而 REST 元数据主机
  `dev.virtualearth.net` 双腿 200——即 auth/endpoint 全通、瓦片永远到不了，叠加 ion 影像路径
  无失败回调 → 地形静默全黑（无影像的本地 TIN 网格=深蓝黑底材）。ArcGIS World_Imagery WMTS
  （`services.arcgisonline.com`，`GoogleMapsCompatible`/Web Mercator，z0–19，免 key）双腿 200 真 JPEG。
- **切换式（either/or）**：任一时刻 tileset 上只有一个影像 overlay。ArcGIS 与天地图同走
  `CesiumWebMapTileServiceRasterOverlay`（baseUrl/layer/style/tileMatrixSetID/format 五字段），
  与 ion asset 2 同用默认 materialKey `"0"` 通道；叠层账保持 3 层（影像 + Clipping + WaterMask），
  **严禁**再叠第二影像层（方案 P1-B 结构性裁定）。
- **自动回落（非单向）**（ArcGIS 与天地图同链）：
  - 触发 1：overlay 级加载失败事件 `CesiumRasterOverlay.OnCesiumRasterOverlayLoadFailure`（仅 tile
    provider 创建失败会广播）。
  - 触发 2：健康探针——每 10 min 对场景原点所在 z7 瓦片发一次与 overlay 同形态的 KVP GetTile
    （约 144 请求/日，对日配额是噪声级），**连续 2 次**非 200/空响应即回落。自有探针是必要的：
    cesium-unity 1.26（cesium-native pin `1bca8021`）逐瓦片配额 403 不进任何 C# 事件
    （`RasterOverlay.cpp:118-131` 只挂 provider 创建路径）。
  - 回落动作：移除现行 WMTS overlay → 挂 ion asset 2 overlay（历史保底；在 a4000 网络上 Bing 瓦片
    不可达，回落后地形会回到暗色底材，属已知边界）。
  - 回落仅**会话内**有效；重新进入 Qingdao 场景（`Open()`）会重读 env 重试——切换双向，不是单向死锁。
- **key 传递路径**（本仓已核）：Unity WMTS 组件不暴露 headers/query 字段，token 只能走 baseUrl
  query（`?tk=<key>`）。pinned cesium-native `WebMapTileServiceRasterOverlay.cpp:111-114` 保留已有
  query 参数并把后续分隔符 `?`→`&`；无花括号 URL 自动选 KVP 模式（`:219-225`）。WMTS KVP 参数名
  按规范大小写不敏感，cesium-native 自身以小写参数发请求，探针与之同形。
- **署名**：ArcGIS World_Imagery 数据来源=Esri, Maxar, Earthstar Geographics, and the GIS User
  Community（代码注释与本文档留档；Unity WMTS 组件无 credit 字段，商用部署前须按 Esri 条款补上屏署名）。

## a4000 远端注入（renderer env）

远端 player 的 env 继承链：`deploy/twin/renderer_control.py` `_spawn_player()` 以
`env = dict(os.environ, DISPLAY=":93", …)` 拉起 Unity Player（`renderer_control.py:134-144`）——
**在启动/重启 renderer 的 shell 里 export 的变量会原样进入 Player 进程**（同链路先例：`SSL_CERT_FILE`
等证书 env）。`TWIN_VIDEO_ROUTE` 等 launcher 侧 env 同理。

```bash
ssh <a4000>
cd ~/.local/share/colav-twin-renderer        # renderer_control.py 所在隔离路径
export TWIN_QINGDAO_IMAGERY=tianditu
export TWIN_QINGDAO_TIANDITU_TOKEN=<控制台取得的 key>
python3 renderer_control.py restart-player   # display/signaling 不动，仅重拉 player
# 验证：
grep -a "imagery source" logs/unity-player.log
#   预期 "[Sango.Qingdao] imagery source: Tianditu WMTS (either/or switch, fallback=ion asset 2)"
# 回退（回 ArcGIS 默认）：
unset TWIN_QINGDAO_IMAGERY TWIN_QINGDAO_TIANDITU_TOKEN   # 或 export TWIN_QINGDAO_IMAGERY=arcgis
python3 renderer_control.py restart-player
```

- macOS 本地（Editor Play / sango-twin.app）同一对 env 变量直接生效。
- token 只经 env 注入，不入库、不进命令行参数（避免 shell history/日志泄漏）；`restart-player`
  之外无需整组重启。

## key 形态口径（2026-10-21 实测定论）

- 用户首个 key（浏览器端类型）对服务端 KVP GetTile 返回 **403 `code=301012`「权限类型为:浏览器端，
  请使用浏览器访问！」**（t0/t1 子域同）——Unity player/探针/curl 全部拒绝，**不可用**。
- **须在 console.tianditu.gov.cn 创建「服务端」类型 key**（同账号免费），注入后按上方步骤验证；
  探针每 10 min 会自动把关，配额/类型问题两次失败即回落。
