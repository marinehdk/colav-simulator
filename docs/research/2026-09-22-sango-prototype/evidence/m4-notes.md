# M4 验收笔记 — 2026-09-29（issue #87）

编排：issue #87 → 两个 workflow（M4-A/M4-B，默认模型子代理）→ 主 agent CUA 验收 → code-review。
范围：`82b997a4..02ee6f13`（66df3521 M4-A / 02ee6f13 M4-B）。EditMode **170/170**（133+31）。

## 验收矩阵

| 项 | 判据 | 结果 | 证据 |
|---|---|---|---|
| 256 档降档 | fps ≥30 默认态航行 | ✅ **87.2–93.8，10 分钟无衰减** | Player.log overlays fps（新会话、零 CUA 采样、无 publisher） |
| 256 档视觉 | V 形艏波仍可读 | ✅ 无量化劣化 | m4a-256tier-sailing.jpg |
| Froude 曲线 | 纯函数+worked-example | ✅ 170/170 含新增 | 门禁 |
| 面板滑条 | 编译+布局不破 | ✅（实机手感留日常使用） | EditMode 全量 |
| census 运行时行 | 编译+语义 | ✅ | EditMode 全量（review 复核） |
| 湿感 | 水线下深色+渐变 | ✅ | m4b-wetness-boot-top.jpg |
| boot top | 暗红横带 | ✅ 无降级 | 同上 |
| 相机摇晃 | B6 时变摆动、B0 静 | ✅ 地平线 -5°→+4s 回正 -2~-3°，俯仰同步 | m4b-sway-b6-t1/t2.jpg + b0 基线 |
| COLREG 光弧 | 左红右绿+±112.5° 扇区+渐隐 | ✅ | m4b-colreg-arcs-night.jpg |
| probe 回归 | 30/30 | ✅ 1.1s | sango_zmq_probe 输出 |

## fps 测量协议教训（账本新增）

- **仪表读数污染源**：CUA 截图采样（settle 等待拖帧环）与 publisher 会话中测得的 19.7–29.7 全部为伪影——独立新会话+零采样复测 87-94 稳定。
- **W1 的 512 档归因部分存疑**（同污染）；256 仍保留为默认（视觉无损已证，成本更低）。
- 干净测量协议：独立会话、无 CUA、无 publisher、读 10s 均值 ≥3 条。

## 挂账

- M1-GlobalVolumeProfile.asset 随 M4-B 提交（644 行 churn，bootstrapper 成对再生）——语义裁决在 code-review。
- 长会话（>10min）+ publisher + CUA 组合下的表现无独立调查项（伪影结论）；若日后演示需长会话录屏，先按干净协议复测。
