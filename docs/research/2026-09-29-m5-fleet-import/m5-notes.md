# M5 验收笔记 — 2026-09-29（免费船队导入批，commit 80ffe0f7）

编排：M5-import-batch workflow（默认模型）+ 主 agent CUA 验收。基线 faa1b642 → 80ffe0f7。

## 验收矩阵

| 项 | 判据 | 结果 | 证据 |
|---|---|---|---|
| EditMode | 全绿 | ✅ 224/224（170+54） | sango/tmp/m5-gate.xml |
| C3 面数闸门 | hero ≤150k 或裁决记录 | ✅ cargo-container 189k/tanker-suezmax 193k → 限中景（本批不减面）；余全部过闸 | m5-audit.md（Unity 实测 tri/贴图/UV/艏向逐船） |
| HDRP 材质 | 无粉紫丢失 | ✅ 自建 HDRP/Lit 全套（Houbei 三材质换装/PC3 14 材质/其余逐船） | m5-initial.jpg 实拍 |
| FCB 换装 | 白壳+绿装+轮胎护舷 | ✅ 融合自然、武器已移除、细节中上、42m 尺度感成立 | m5-fcb-close.jpg |
| M4 工艺迁移 | decal 随新主角生效 | ✅ 航行中 V 形艏波+艉部白沫；浮态自然 | m5-fcb-sailing.jpg |
| 尺度归一 | 相对尺度合理 | ✅ 油轮明显大于巡逻艇；Houbei 导入 +2133% 缩放由编目 LOA 归一化修正（实测视觉正确） | 同上 + audit 表 |
| probe | 30/30 | ✅ 1.3s | 会话输出 |
| fps | 干净协议 ≥30 | ✅ 61.9/78.8/73.4（全新会话零采样无 publisher；含全船队，较 M4 的 87-94 降 ~15-25%＝船队真实成本，预算内） | Player.log |
| 清场 | Assets 无 zip/glb/DS_Store | ✅ 档案移 tmp/m5-archives；Quaternius/.zcode 误写已清 | ls 核验 |

## 挂账

- cargo-container/tanker-suezmax 减面与 LOD（M6+ polish 或远景替代）
- Blender GLB→FBX 转换脚本 tools/convert_glb_to_fbx.py 已版本化（可重跑）
- Houbei hero 近景仍为中档（17.7k tri）——hero 精模维持外包推迟轨道
