# sango-fusion-s5 — P3-S5 IPDA 存在概率贯通 + 置信度发布 + 高置信航迹数据产品（spec #90）

生成日期：2026-10-03。断点三层修法与行号见 commit message（P3-S5）。

## 产物

| 文件 | 内容 |
|---|---|
| `track-compare.json` | god vs vimmjipda 同 seed 航迹对拍统计（scenario=crossing_stand_on，dt 0.5s，600s，seed 2026） |
| `confirmed-tracks-sample.json` | vimmjipda 融合航迹末帧的 confirmed-tracks 信封（真实管线产出，schema `sensor-model@1/tracks`） |
| `confirmed-tracks-live.json` | live god 会话 `GET /api/sessions/{id}/confirmed-tracks` 实测响应 |
| `live-envelope-extract.json` | live 会话 WS `truth[].tracks` §6 三平行数组实测（existence_prob/quality/sources） |
| `tracks-live-2d.png` | live 2D 海图：tracks 层存在概率着色点（god=全绿 confirmed） |
| `tracks-live-legend.png` | 图例：存在概率 ≥0.9（绿）/ 0.5–0.9（琥珀）/ <0.5（灰）三档 |
| `tracks-live-card.png` | 2D 目标卡 TS1：CONF 行 = 1.000 P |
| `evidence-status.json` | probe 断言清单 |

## 复现命令

```bash
# 1) god vs vimmjipda 对拍 + confirmed-tracks 样例（无需后端/浏览器）
.venv/bin/python tools/sango_track_compare_s5.py \
    --scenario scenarios/crossing_stand_on.yaml \
    --output output/sango-fusion-s5/track-compare.json
#   容差定义内嵌 JSON.tolerances：god RMSE ≤ 1e-6 m（真值直拷）；
#   融合侧 RMSE report-only（外部 IPDA 无 oracle 门）；关联门 200 m/帧最近邻。

# 2) live E2E（须 8010 后端；后端代码变更后先 kickstart 重载并等 ~45s）
launchctl kickstart -k gui/$(id -u)/com.marine.colav-simulator.frontend
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh" && nvm use 22
node tools/sango_tracks_s5_probe.mjs        # 默认 tracker=god（能力策略唯一可选）
```

## 阈值语义（报告 07 §2.2 / 契约 §4 锚定）

- 决策升级门 `PlannerOddProfile.existence_escalation_threshold = 0.5`（保守默认：仅当
  tracker 自身判定"缺席概率更大"时才扣留升级；缺省字段=1.0 永不扣留，God=1.0 不变）。
- confirmed-tracks 数据产品默认门 `CONFIRMED_TRACKS_DEFAULT_THRESHOLD = 0.999`
  （= 契约 §4 track_mgmt.confirm_threshold；milliAmpere 语义 = 确认航迹才进运动规划）。
- live 会话受产品能力策略限制只能选 god（capabilities.py:213）→ 截图为全绿 confirmed 档；
  琥珀/灰档着色由 `tests/web_gui/situation-display.test.mjs` 单测钉死，KF 侧数值见
  `confirmed-tracks-sample.json`（vimmjipda r=0.9999989 → confirmed）与
  `track-compare.json`（KF 递推衰减见 test_tracker_snapshot_contract）。

## 相关测试

```bash
.venv/bin/python -m pytest tests/ -q -k "sensor or tracker or observation or compact or transport or radar_x or mast or georef or lidar or ais or ipda or track"
node --test tests/web_gui/*.test.mjs
```
