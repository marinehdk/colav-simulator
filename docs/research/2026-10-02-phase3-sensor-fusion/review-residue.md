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

- **P3-11 关闭（spec #91 前置批，2026-10-03）**：根因 = `MastSensorRig.Attach` 的
  SetParent 环——rig 与槽位工厂同 GO（旧场景烘焙），Attach(槽位) 是环被 Unity
  6000.3.24f1 **静默拒绝**（批模式实证：无异常无日志、层级不变），且旧 Detach 清空
  rig transform 全部子物体 = 顺带毁掉槽位船（Player.log 双份 rig 构建的来源）；另
  视口相机恒随 demo 船（followShip 未重挂 + BridgeCameraMount 焊死 demo 船）。
  修复：rig 独立子 GO 烘焙（TwinBridgeSceneBuilder）+ Attach 环目标显式拒绝 +
  Detach 只毁自建 mount + followShip 重挂/mount 让位/ship-relative（detach 全还原）。
  证据：EditMode `MastSensorRigAttachTests`/`TwinBridgeFollowRetargetTests`；
  census `cam view=Bridge pos=(402.5,11.7,399.1) followPos=(429.1,-0.3,429.0)`；
  userpath `output/sango-userpath/slot-parity.json`（diag↔truth 槽位位姿对拍
  0.13 m / 0.08°）。
- **P3-12（新，spec #91 前置批发现，场景注册设计项）**：twin 会话的锚定（live =
  本船首帧 UTM、replay = ENC origin）把航行区投到 M6 海峡场景的**陆地贴图上**
  （camera_free 空中取证：走廊 (500..2500)² 上空为城镇/森林地形，demo 舰水域在
  (-1500,-5000) 一带；`output/sango-userpath/` 截图组）。目标船槽位位姿正确
  （P3-11 对拍）但视觉上没入地形——"live 画面目标船肉眼可见"需场景注册决策
  （M6 地形重配准到 ENC / twin 专用水面环境 / 混合），属 Unity 场景资产级工作，
  非代码缺陷。处置：**转后续立项**（用户决策场景方案）；userpath 探针以
  槽位位姿对拍 + census 双证替代"肉眼可见"断言（断言不降：数据面闭环），
  terrain 取证截图随探针产物在盘。

## 关票检查单

- [x] P1-1 双管（接线 + 披露）
- [x] P2-2 数值 artifact 在盘
- [x] P3-5 / P3-7 就地修
- [x] 本台账（P3-3/4/6/8/9/10 + 指针）
