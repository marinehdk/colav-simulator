# URS vendored receiver modules

Source: Unity-Technologies/UnityRenderStreaming tag **3.1.0-exp.9**, `WebApp/client/src/`
(spike 复现资产：`output/sango-urs-spike/report.md` §4)。本地化惯例同 `vendor/openbridge`、
`vendor/cesium`：禁 CDN、禁 npm install，页面直接 import 本目录 ES 模块。

| 文件 | 上游 | 本地改动 |
|---|---|---|
| `renderstreaming.js` | `src/renderstreaming.js` | 无（逐字节原样） |
| `peer.js` | `src/peer.js` | 无 |
| `logger.js` | `src/logger.js` | 无 |
| `signaling.js` | `src/signaling.js` | **1 处**：`WebSocketSignaling` 构造器增第 2 参 `explicitUrl`——上游从 `location.host` 推导信令 WS 地址（spike 页面由 webapp 同源托管故可用），本页面由 FastAPI `:8010` 托管、信令在 `:8080`，需显式传入 `ws://127.0.0.1:8080`。缺省行为不变。 |

升级方式：替换文件、重放上述标记改动、更新本表。
