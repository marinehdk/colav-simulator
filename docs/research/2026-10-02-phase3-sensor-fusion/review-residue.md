# 阶段3 终审台账（spec #90 关票前置，2026-10-02）

双轴终审 REQUEST-CHANGES 修复批的残留台账：P1-1/P2-2/P3-5/P3-7 就地修（见
[self-review.md](self-review.md) 终审修复批增补段），其余 P3 逐条记录如下。
处置词汇：**已评审接受**（留尾已写档/边界内，不动作）｜**转后续**（另立小批，不阻塞关票）。

## P3 就地修（指针）

| 项 | 处置 | 指针 |
|---|---|---|
| P1-1 相机量测未通 KF 链 | 修复（双管：接线 + 披露） | `external_cameras:` 场景键 + 仿真级关联；同级披露见 [00-PLAN.md](00-PLAN.md) §7 与 [self-review.md](self-review.md)；E2E 因果证 `tools/sango_twin_camera_probe.mjs`（`output/sango-twin-camera/report.md`：LEG ON camera-source confirmed track existence 0.9995 sources=[2]；LEG OFF 衰减出列 + accepted_frames 冻结） |
| P2-2 georef 误差存证缺失 | 修复 | `output/sango-twin-s2/georef-error-stats.json`（pytest `tests/test_georef_error_stats.py` 产出，纯函数层） |
| P3-5 `web_gui/modules/situation-display.js:809` applyOwnshipFollowView 零尺寸 | 修复 | fitENCView 同款闸（:788 先例）；web 单测 `tests/web_gui/situation-display.test.mjs`（P3-5 例） |
| P3-7 `tools/sango_detector_service.py` forward sensor_id 硬编码 2 | 修复 | `mount_sensor_id()` 按 `--forward-mount` 查 `colav_simulator/core/mast_cameras` 标定表（最小实现=直接 import，stdlib-only 表，.venv-detector 实测可导入）；ZMQ 主路径零变化 |

## P3 残留（逐条）

- **P3-3（Standards）**：`colav_simulator/integrations/vimmjipda_existence.py:61-62` 适配器
  `observed_at_s/generated_at_s` 占位 0.0（`get_track_information` 消费者拿无意义时戳；
  外部接口无每航迹时戳）。处置：**已评审接受**（S5 留尾已写档，外部仓接口限制）。
- **P3-4（Standards）**：`gui_server/main.py confirmed_tracks` god 会话数据产品合成
  `sensor_id=1, age=None` 源项（schema sources min_length=1 迫使）；docstring 已声明
  boundary convention，但 JSON 消费者无法区分合成/实测（schema 见
  `colav_simulator/schemas/sensor_model_v1.py:196`）。处置：**已评审接受**，后续 schema
  若演进加 synthetic 标记。
- **P3-6（Standards）**：`web_gui/*` 多处 situation-display.js 现 4 个版本 token 并存
  （20260826/20260920/20260923/20261003）同页 4 次模块求值——预存分裂；本批只 bump 3 个
  stateful 边（hang-rootcause 明示），纯 helper 边持旧 token。处置：**转后续清理批**
  （与既有"版本串唯一性守护测试"方向合并，非本批）。
- **P3-8（Spec 记录）**：`colav_simulator/core/sensing.py` `generate_sfd_frame`/`sfd_records`
  无运行时消费者（仅测试）——sensor-model §3 量测流生成器是休眠脚手架；WS 交付走 §6
  平行数组（契约允许传输载体自选）。处置：**已评审接受**（留尾已写档）。
- **P3-9（Spec 记录）**：`web_gui/modules/replay-source.js` S4 留尾"回放器 AIS 数据回填
  留 S5"未做且未再披露（S5 只加了 tracks 三数组透传）。处置：**转后续**（回放器 AIS
  回填小批）。
- **P3-10（Spec 记录）**：`colav_simulator/core/sensing.py` legacy AIS 传感器仍以 GT 关联
  进 KF 主链，契约 §2 表标 AIS 旁路——预存路径，契约管新流；`trackers.py` 注释自称覆盖
  "ais-vocab" 但实际不挡 legacy AIS。处置：**已评审接受**（legacy 语义保留），注释失配可
  在后续批顺手改注释。

## 修复批新发现（本批 E2E 期间暴露，非终审清单）

- **P3-11（新，Unity 侧）**：sango twin live 模式不渲染本船前方的他船槽位（`attached
  ships=2`、WS truth 位置正确，桅杆 EO 馈送与视口均无目标船影像；环境锚泊船群正常渲染）。
  相机因果 E2E 因此改走 `sango_detector_replay.py` + 合成帧（真实桅杆渲染 + 目标贴其
  georef 投影像素框）——真 YOLO 服务、真 observations 端点、真关联/KF 链路不受影响；
  见 `tools/sango_twin_camera_probe.mjs` 与 `output/sango-twin-camera/report.md`。
  处置：**转后续**（Unity 渲染排查/立项，本批 Unity 零改动纪律内不追）。

## 关票检查单

- [x] P1-1 双管（接线 + 披露）
- [x] P2-2 数值 artifact 在盘
- [x] P3-5 / P3-7 就地修
- [x] 本台账（P3-3/4/6/8/9/10 + 指针）
