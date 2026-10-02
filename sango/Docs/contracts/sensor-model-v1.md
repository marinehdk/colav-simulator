# sensor-model-v1 — SFD 传感器模型与融合输入契约（P3-S0，spec #90）

状态：**已冻结**（2026-10-02，P3-S0）。方向：**量测流生成器/后端感知层 ↔ 融合跟踪器 ↔ 数据产品**。
来源：`docs/research/2026-10-02-phase3-sensor-fusion/milliampere-ch5-fcb45-layout.md` §6 草案转正
（Autoferry SFD 格式扩展，`2026-09-30-mass-situational-awareness/04-multi-sensor-fusion-ipda.md` §2.5）。
Python 权威形状：`colav_simulator/schemas/sensor_model_v1.py`（pydantic v2，extra=forbid）；
契约测试：`tests/test_sensor_model_v1_contract.py`（§7 样例字面量同源对拍）。

**边界：Unity/C# 不消费 SFD。** Unity 只做视景与原始帧发布（frame-publisher-v1），不做目标裁决
（00-PLAN §1 铁律 1）；量测/杂波/遮挡/融合/置信度全部 Python。故本契约无 C# DTO、无 EditMode 回环——
与 twin-bridge-v1 / detection-result-v1 的双侧对拍工艺在此**不适用**。

## 1. 语义与范围

- v1 覆盖：X 波段雷达（radar_x）、白光相机（camera_eo）、红外相机（camera_ir）三源进融合；
  LiDAR（lidar）与 AIS（ais）为**旁路通道**（显示/近距接触点，不进 IPDA——00-PLAN §3 铁律 3、报告 04 开放问题 5）。
- 坐标：全部量测已同构到 **ownship-NED 水平面 NE 米制**（北东序，`[north, east]`；world = UTM 48N）。
  EO/IR 原始方位量测与像素框的 georef 在生成器/后端边界内完成（NED/ENU 转换不越界——报告 01 坐标坑）。
- 本契约为**数据 schema**；传输载体（进程内 list / jsonl / ZMQ）由实现段自选，v1 不冻结传输。

## 2. sensorID 词汇（冻结，Autoferry SFD 原序的刻意重排）

| sensor_id | sensor_label | 通道 | 进融合器 |
|---|---|---|---|
| 1 | `radar_x` | X 波段雷达 | 是 |
| 2 | `camera_eo` | 白光相机（桅杆阵列/PTZ） | 是 |
| 3 | `camera_ir` | 红外相机（桅杆阵列） | 是 |
| 4 | `lidar` | LiDAR 点云 | **否（旁路）** |
| 5 | `ais` | AIS 报文 | **否（旁路）** |

注：Autoferry SFD 原序为 Lidar:1/Radar:2/IR:3/EO:4——本契约重排为雷达首位（主测距源）、相机次之、
旁路殿后。外部 vimmjipda 集成（`colav_simulator/integrations/registry.py:122` 动态加载）若按
Autoferry 序索引传感器，映射在量测流生成器边界内完成（S5 面），本词汇不出后端。

## 3. 量测流消息（逐条）

```json
{"schema_version":"sensor-model@1","frame_id":"ownship_ned","t_s":12.4,"sensor_id":1,"sensor_label":"radar_x","mount_id":"mast_top_xband","measurements":[{"sensor_id":1,"target_hint":null,"position_ne_m":[1520.5,-310.25],"position_cov_ne_m2":[[64.0,0.0],[0.0,64.0]],"t_s":12.4,"confidence":0.92,"class_name":null,"class_confidence":null}],"ownship_pose_at_measurement":{"p_n":6955012.25,"p_e":37012.5,"yaw":1.5708,"pitch":0.0,"roll":0.0},"epoch_unix_ns":null}
```

```json
{"schema_version":"sensor-model@1","frame_id":"ownship_ned","t_s":13.1,"sensor_id":3,"sensor_label":"camera_ir","mount_id":"mast_ir_bow","measurements":[{"sensor_id":3,"target_hint":null,"position_ne_m":[620.75,95.5],"position_cov_ne_m2":[[36.0,0.0],[0.0,121.0]],"t_s":13.1,"confidence":0.71,"class_name":"ship","class_confidence":0.83}],"ownship_pose_at_measurement":{"p_n":6955012.25,"p_e":37012.5,"yaw":1.5708},"epoch_unix_ns":1738368000000000000}
```

```json
{"schema_version":"sensor-model@1","frame_id":"ownship_ned","t_s":14.0,"sensor_id":5,"sensor_label":"ais","mount_id":"mast_vdl","measurements":[{"sensor_id":5,"target_hint":2,"position_ne_m":[900.0,-40.0],"position_cov_ne_m2":[[25.0,0.0],[0.0,25.0]],"t_s":13.6,"confidence":1.0,"class_name":null,"class_confidence":null}],"ownship_pose_at_measurement":{"p_n":6955012.25,"p_e":37012.5,"yaw":1.5708},"epoch_unix_ns":null}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | string | 是 | 恒 `"sensor-model@1"` |
| `frame_id` | string | 是 | 恒 `"ownship_ned"`（v1 唯一帧系；世界系 UTM 48N NE 米制） |
| `t_s` | float | 是 | 帧仿真钟秒（与后端 `simulator.t` 同域） |
| `sensor_id` | int | 是 | §2 词汇 |
| `sensor_label` | string | 是 | §2 标签，必须与 `sensor_id` 一致 |
| `mount_id` | string | 是 | 桅杆挂点标识（FBX 锚点命名，如 `mast_top_xband`/`mast_ir_bow`；布局见 milliampere-ch5 §4.2） |
| `measurements` | array | 是（可为空） | 量测记录（下方）；空数组 = 本帧该传感器权威"无量测" |
| `measurements[].sensor_id` | int | 是 | 与帧 `sensor_id` 一致（记录自包含） |
| `measurements[].target_hint` | int\|null | 是 | do_idx 关联提示；AIS = mmsi→do_idx 映射结果，radar/camera = null |
| `measurements[].position_ne_m` | float[2] | 是 | `[north_m, east_m]`（ownship-NED） |
| `measurements[].position_cov_ne_m2` | float[2][2] | 是 | 对称、对角非负；相机量测呈径向拉长（报告 04 E5 形态样例：σ_N=6m/σ_E=11m） |
| `measurements[].t_s` | float | 是 | 单量测时戳（≤ 帧 `t_s`；AIS 龄期语义 = 帧 `t_s` − 记录 `t_s`） |
| `measurements[].confidence` | float 0-1 | 是 | 单量测检测/完整置信；AIS 报文恒 1.0 |
| `measurements[].class_name` | string\|null | 是 | 类别（`ship`/`boat`/…）；radar v1 = null |
| `measurements[].class_confidence` | float 0-1\|null | 是 | 有 `class_name` 才可给 |
| `ownship_pose_at_measurement` | object | 是 | `{p_n,p_e,yaw,pitch,roll}`——量测时刻 ownship 位姿（NE 米 + rad） |
| `epoch_unix_ns` | int\|null | 是 | 真实硬件回放钟（GNSS PPS）；纯仿真 = null |

## 4. 生成器退化参数（VIMM 标定锚，内嵌冻结）

```json
{"noise":{"lidar_sigma_c_m":6.6,"radar_sigma_r_m":8.0,"radar_sigma_theta_rad":0.017453292519943295},"visibility":{"w11":0.9,"w01":0.52,"global_pd":0.92,"fov_outside_pd":0.0},"clutter":{"poisson_rate_per_m2":5e-07,"new_target_rate_per_m2":1e-07},"async_jitter":{"radar_scan_period_s":2.5,"drop_probability":0.0},"track_mgmt":{"confirm_threshold":0.999,"delete_threshold":0.01,"terminate_after":6}}
```

- `noise`：VIMM 标定量测噪声，σ 经雅可比投影（E5 形态）。
- `visibility`：逐类可见性 Markov 链 ω₁₁=0.90/ω₀₁=0.52 + 全局 PD=0.92 + FOV 外 PD=0。
- `clutter`：单位面积泊松杂波 5×10⁻⁷/m² + 新目标 10⁻⁷/m²。
- `async_jitter`：雷达扫描周期 2.5s（24rpm 远档）|1.0s（60rpm 近档，量程联动）+ 概率漏检。
- `track_mgmt`：IPDA 确认/终止 Tc=0.999/Td=0.01/6 拍（vimmjipda 外部仓库，registry 加载不可用即抛错）。
- 全部值溯源：milliampere-ch5 §6 → 04 报告 §2.5。`SfdGeneratorConfig` 默认值 = 本表（契约测试钉死）。

## 5. 确认航迹输出（融合器 → COLAV/数据产品）

```json
{"schema_version":"sensor-model@1/tracks","t_s":14.0,"tracks":[{"track_key":"7:1","target_id":7,"generation":1,"existence_prob":0.997,"quality":0.88,"sources":[{"sensor_id":1,"last_seen_age_s":0.4},{"sensor_id":5,"last_seen_age_s":1.2}],"position_ne_m":[1520.5,-310.25],"velocity_ne_mps":[-6.2,0.3],"heading_rad":3.124,"position_cov_ne_m2":[[49.0,0.0],[0.0,49.0]],"class_name":"ship","class_confidence":0.83}]}
```

- `track_key` = `"{target_id}:{generation}"`（仓库 `TrackKey` 语义，trackers.py:54）。
- **`existence_prob` 语义警示**：虚警预算标定出的**门控量**（报告 07 §2.2），决策侧禁止读成目标存在概率
  真值；ECC19 门控先例 = 超阈值才交 MPC。决策消费接线属 S5（IPDA 三层断路修复）。
- `quality` ∈ [0,1] 复合质量（NIS/龄期/源数合成，S5 定义）；`sources[]` = 贡献传感器 + 龄期。
- 旁路通道（lidar/ais）可出现在 `sources[]`（佐证显示），但自身不独立产生融合航迹。

## 6. WS 全量 transport tracks 加性置信度字段（D 交付）

全量 1.0 transport 已含 tracks（`gui_server/main.py:1236` → `_local_tracks` :1572-1587，
平行数组 labels/generations/states/covariances/nis）。P3 **只加三个平行数组字段**，旧发布端/旧 web 零破坏：

```json
{"labels":[7],"generations":[1],"states":[[1520.5,-310.25,-6.2,0.3]],"covariances":[[[49.0,0.0],[0.0,49.0]]],"nis":[2.31],"existence_prob":[0.997],"quality":[0.88],"sources":[[{"sensor_id":1,"last_seen_age_s":0.4},{"sensor_id":5,"last_seen_age_s":1.2}]]}
```

- `existence_prob[]`/`quality[]`：与 `labels[]` 等长的平行数组（`TracksSnapshotV1` 校验）。
- `sources[]`：每航迹的 `TrackSourceRef` 列表（sensor_id + last_seen_age_s）。
- 发布路径：全量 1.0 加字段零破坏（web `JSON.parse` 宽松消费）；**compact-v1 剥除策略不动**
  （`_compact_stream_payload` `main.py:179` 名单本段不改，感知字段仍被剥除；compact 侧演进若需要属 S5，
  须同步 sango `ColavTelemetry` 子集声明——repo-sensor-seams §5 警告）。

## 7. 验收钩子与冻结样例

- 契约测试：`tests/test_sensor_model_v1_contract.py` —— §3/§5/§6 样例字面量反序列化 + 违约拒绝
  （非对称协方差/标签失配/sensorID 越界/未知字段/平行数组不齐）+ VIMM 默认值锚。
- 双侧对拍：本文档样例 ↔ 测试字面量同源（修改须两处同步）。
- SFD 消费者：S2 相机链（observations georef 产出）、S1 雷达生成器、S5 融合贯通——三段实现以本契约为准。

## 8. 演进记录（只加条款）

| 日期 | 段 | 变更 | 溯源 |
|---|---|---|---|
| 2026-10-02 | P3-S0 | 契约冻结（§1-§7）；sensorID 重排裁决；VIMM 标定锚内嵌；WS tracks 三加性字段 | spec #90 |
