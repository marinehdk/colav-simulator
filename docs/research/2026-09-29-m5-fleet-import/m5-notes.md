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

## Code-review 处置（2026-09-29）

- **F1（Blocker 判定）→ 实机裁决为误报**：评审员静态推演认为归一化烘在 prefab 根位、被放置层覆盖致 7/8 艘错位。三重反证：①prefab 全量 transform dump（14 块）——根节点干净 (0,0,0)/scale1，所引"根 p.y=+6.237"不存在于文件（+6.24 为轮胎辅助节点值，归属误读）；②实机三组帧（主角水线/轮胎贴水/艏波、俯视锚地零沉没零悬空零穿模——m5-fleet-topdown.jpg）；③评审自认仅静态分析建议 GUI 确认。**底层关切成立**（契约无测试/审计无 center）→ 加固批进行中（落位位姿断言测试+审计 center 列）。
- F2 署名文本补 URL+CC deed 链（8 行）✓ 6c9346ff；F3 docstring 改正 ✓ 同 commit。
- F4 双表联动测试 → 加固批；F5 meta 两行格式=Unity 会自动补齐（评审自评无害），不动。
- 范围口径：评审指出 faa1b642..80ffe0f7 混入 M6-spike 提交（信息项，M5 单提交=ab8e4446..80ffe0f7）——记录。
