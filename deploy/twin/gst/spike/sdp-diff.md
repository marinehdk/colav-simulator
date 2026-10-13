# SDP 差异台账 — webrtcbin sender vs Unity 样例(M2,2026-10-13)

判据口径(DESIGN §2 M2 验收 1):**功能(Chrome 实际解码)而非逐字段复刻**。
本台账逐项记录 GStreamer 1.24.2 webrtcbin 生成的协商报文与 Unity 真实样例
(a4000 `logs/signaling.log` / `logs/unity-player.log`,session b8dea240/0f458055)
的已知差异。每项注明:是否影响 Chrome 互通(实测)、工程处置。

对照文件(实测捕获,a4000 `~/gst-spike/bench/spike/sdp/`):
`final-offer1`(浏览器 offer#1)/`final-answer1`(我们 answer#1)/
`final-offer2`(我们 offer#2)/`final-answer2`(Chrome answer#2)。

## 1. 结构性差异(webrtcbin 生成器特性)

| # | 项 | webrtcbin(实测) | Unity(实测样例) | Chrome 互通影响 | 处置 |
|---|---|---|---|---|---|
| D1 | offer#2 m=video direction | `a=sendonly`(经 sink pad 的 transceiver 直设;`get-transceivers` 返回 GLib.Array pygi 不可迭代,`add-transceiver` 会另造一条 m-line,均实测) | `a=sendonly` | 无(answer#2 Chrome 回 `a=recvonly`) | 已达成 sendonly ✓ |
| D2 | `a=fmtp` 行 | **无**(sink caps 钉 packetization-mode/profile-level-id 也不透传;且 `profile-level-id=42e033` 会被 caps 解析器当科学计数法 double `4.2e34`,与浏览器 answer 的 `(string)` 型 ptmap 不匹配 → 推流 not-negotiated,实测踩坑) | `a=fmtp:123 level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42e01f` | 无(Chrome answer#2 自带 fmtp 42e01f;实测 1440p30 解码) | RTP caps 只留 `media/encoding-name/payload/clock-rate` 四字段;profile 一致性以功能解码覆盖(见 §2) |
| D3 | rtcp-fb 集 | `nack pli` + `ccm fir` + `transport-cc`(无 goog-remb、无裸 nack;webrtcbin 不实现 REMB) | 同左 + `goog-remb` + 裸 `nack` | 无(内网 P2P 零丢包;remb 仅影响带宽估计) | 记录;公网化时再议(DESIGN R9) |
| D4 | mid 命名 | `0` / `video0` | `0` / `1` | 无(浏览器侧无 mid 值匹配依赖;信封 candidate 里 mid 走 mline 数字回退) | 记录 |
| D5 | BUNDLE | `a=group:BUNDLE 0 video0`(**必须显式 `bundle-policy=max-bundle`**;默认 none 时各 m-line 独立 transport,视频 transport ICE 不通,首帧后发送侧阻塞,实测) | `a=group:BUNDLE 0 1` | 无(一致语义) | sender 已设 max-bundle ✓ |
| D6 | 视频 m-line 端口 | `m=video 0` + `a=bundle-only` + `a=rtcp-mux-only` | `m=video 9` | 无(Chrome 接受) | 记录 |
| D7 | 候选携带 | 全 trickle(on-ice-candidate 单发;answer#1 SDP 内无候选) | answer#1/offer#2 SDP 内联 host+srflx 候选(ICE gathered 后才发) | 无(1.2s 级建连) | 记录;sender 候选数 16/连接 |
| D8 | ICE 候选类型 | 仅 host(libnice,无 STUN) | host + srflx(Unity 默认 STUN) | 无(内网同网段) | 公网化时需加 STUN 配置 |
| D9 | answer#1 setup | `a=setup:active`(webrtcbin 为 DTLS client) | `active` 或 `passive`(两次样例各一见) | 无 | 记录 |

## 2. 编码 profile 一致性(R10 收口)

- 协商面:我们 offer#2 无 fmtp(D2);Chrome answer#2 对 PT123 报
  `profile-level-id=42e01f`(constrained-baseline L3.1,含 `level-asymmetry-allowed=1`)。
- 实际码流(独立复核,非依赖协商):容器内 6s 编码 dump
  `~/gst-spike/bench/spike/prof-check.h264` 逐 SPS 解析 +
  sender 运行期 SPS 探针,一致输出 **profile_idc=66(Baseline)、constraint_flags=0xC0、
  level_idc=50(L5.0)**。
- 即:码流 Baseline@L5.0 ⊂ Chrome 声明的 constrained-baseline 档(42e01f)外加
  level 上浮 —— Chrome 实测照常解码(1440p30 全程 0 drop)。
- 备注:`nvautogpuh264enc cabac` 属性默认 true,但 `preset=p4 tune=ultra-low-latency`
  下实际输出 Baseline(无 CABAC)——属性与输出不一致,以码流为准记录。
  M1 笔记"cabac 默认 true → High 类输出"的推断据此修正。

## 3. webrtcbin 1.24.2 行为怪癖(M2 实测踩坑,全部已在 sender.py 处置)

| # | 现象 | 处置 |
|---|---|---|
| Q1 | `notify::ice-connection-state` 不触发(属性恒 `new`),`notify::connection-state` 正常到 `connected` | 挂视频钩子双轨监听 connection-state |
| Q2 | 收到 RTCP PLI 不产生上游 GstForceKeyUnit(丢包注入 0.5s/550+ 包实测 `fku=0`;恢复依赖 gop=60/2s 周期 IDR,浏览器 1 个采样周期内恢复) | R2 残留:gop 上界 2s;M3 若需更快恢复可缩短 gop 或周期 force-keyunit |
| Q3 | 无 transport 时 sink pad 收 buffer → `not-negotiated` 流错误杀死支线;未链接的 pay.src 推流同样报错 | 编码支线元素建后保持 READY,answer#2 SRD 完成后再 sync(主循环线程执行) |
| Q4 | create-offer 与 sink pad caps 事件竞态可打死支线 | m-line 由 `request_pad_simple`+pad.transceiver 方向直设,不依赖 caps 事件时序 |
| Q5 | pygi:`get-transceivers` 返回 GLib.Array 不可迭代/无 len;`reply.get_value()` 返回非持有引用(promise 回调后访问即 segfault);promise change-func 回调实际多传一参;`Gst.Promise.reply()` 手动回复会 segfault | pad.transceiver 直取;回调内立即取 SDP 文本副本;回调签名 `*_`;不手动 reply |
| Q6 | caps 字符串 `profile-level-id=42e033` 解析为 double(科学计数法) | 见 D2,四字段 caps |

## 4. 信令信封(非 SDP 正文)对拍结论

逐字段一致(样例:a4000 `logs/unity-player.log` 0f458055 段、`logs/signaling.log`
b8dea240 段;我们侧 `~/gst-spike/bench/spike/wslog-*.jsonl`):sender 三种上行帧
`answer/offer/candidate` 的 `from/to/type/data` 键序与值类型(含 candidate 的
`sdpMid` string、`sdpMLineIndex` int)与 Unity 一致;Unity answer/offer data 尾部
历史上存在 `type+polite` 字段两变体,sender 按现役 player 样例带上
(服务器只消费 `data.connectionId`+`data.sdp`,其余透传忽略)。详见笔记 02 §5。
产品怪癖(实证据):浏览器上行 candidate 的 `data.sdpMid` 与 `data.sdpMLineIndex`
互换(`peer.js:34` → `renderstreaming.js:140` 参数序),视频 m-line 上到达 sender 时
形如 `sdpMLineIndex='video0'`;Unity 侧靠 application-only/巧合 mline 容忍,
sender 侧按 BUNDLE 回退 mline=0/1 处理。
