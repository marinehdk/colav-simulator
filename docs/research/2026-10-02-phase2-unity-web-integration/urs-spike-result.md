# URS spike 结论（P2-S2 嵌入决策门，Mac 单机）— PASS

- 日期：2026-10-02 · 任务：spec #89 P2-S2 · 完整证据与复现命令：`output/sango-urs-spike/report.md`
- 判据（00-REPORT §6 P2-S2）四条全过 → **URS 3.1.0-exp.9 可用作 sango 像素流主线（Mac 侧实证）**。

## 逐条结果

| 判据 | 结果 | 关键数字 |
|---|---|---|
| ① 交互延迟 ≤250 ms | PASS | 玻璃到玻璃中位 **116 ms**（5 样本 114–135 ms，最坏上界 193 ms）；getStats：30 fps 满、jitter 16–24 ms、解码 ~2 ms/帧、jitter buffer ~38–41 ms、0 NACK/0 PLI |
| ② HDRP 渲染零降级 | PASS | 浏览器 `<video>` 与编码器输入 RT 同刻对照逐项一致（日桥楼 / TopDown / 夜间三态）；夜间号灯（红绿舷灯）流内清晰；~4.5 Mbps @720p30 |
| ③ 断线可重连 | PASS | 页面重连：建连 0.11 s、视频 ~1.1 s；杀 standalone player（SIGTERM 干净退出）→ 重拉 `open` 起 **~5.6 s** 恢复视频 |
| ④ DataChannel 双向 JSON | PASS | `spike-echo` JSON echo **RTT 中位 5.9 ms**（n=128）；浏览器 JSON 命令驱动 Unity（切视角/昼夜/按键，日志+画面双证据）；原生输入链路（InputRemoting→InputSystem 注入 Keyboard1）打通 |

## 装包兼容性结论（Unity 6000.3.24f1 + HDRP 17.3）

1. registry 解析成功（webrtc 3.0.0-pre.8、inputsystem 解析至 1.20.0）。
2. **唯一编译错误**（Editor 程序集一处）：`RenderStreamingWizard.cs(25,62): error CS0619: 'AndroidSdkVersions.AndroidApiLevel22' is obsolete…`（Unity 6 移除该枚举）。修复 = 嵌入式包 `sango/Packages/com.unity.renderstreaming/`（3.1.0-exp.9 原文 + 1 行 `AndroidApiLevel22→25`）；Runtime 全链路零改动零错误。
3. macOS player 构建需 `cameraUsageDescription` + `microphoneUsageDescription`（URS 引用 WebCamTexture/Microphone 触发隐私清单校验）；输入回传需 `activeInputHandler: 2`（Both）。
4. **EditMode 451/451 保持全绿**（嵌入式包自带 19 个测试已按 vendor 惯例裁剪；其中 1 个为该包联网验证测试，超时与项目代码无关）。
5. standalone player 构建成功（`Builds/sango-urs-spike.app`，382 MB）——部署形态在 Unity 6 上成立。

## 遗留（不阻塞门，落地 S3 处理）

- URS `AutomaticStreaming` 默认设置在 player 里有 `:80` 冗余信令重试噪音（以 `RenderStreaming.AutomaticStreaming=false` 或项目 settings 资产关闭）。
- 编辑器 GUI 在 play 中被 SIGTERM 后自身重启有概率卡死（licensing 后、项目加载前；batchmode 与全新工程均正常，与 URS 无关）——生产形态是 player + supervisor，不依赖编辑器 GUI 重启；单独立案。
- 延迟构成与调研档口径一致（jitter buffer 主导）；a4000（Linux+NVIDIA/X11/Vulkan/NVENC）风险面仍按调研档 §2.3 单独实测。
