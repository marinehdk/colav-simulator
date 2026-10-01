# detection-return-v1 — 检测结果回传线上协议（M9，回传侧新建）

状态：已冻结（2026-09-30，M9）。方向：**YOLO 检测服务 → Unity（Sango 消费端）**。
payload 契约：`detection-result-v1.md`（字段冻结不变，本文只冻结传输/新鲜度/开关）。
实现：`Assets/Scripts/Runtime/DetectionResultConsumer.cs`（适配层）+ `Vessels/DetectionFreshness.cs`（seq/age 谓词与 live/GT 判定纯函数，EditMode 已测）+ `DetectionOverlay.cs`（live/GT 双路渲染）。
服务端先例：`tools/sango_detector_service.py`（pyzmq + ultralytics）；无 Unity 联调：`tools/sango_detector_replay.py`。

## 1. 传输

- 上游：SUB connect `tcp://127.0.0.1:5556` 消费 `sango.frame`（frame-publisher-v1，不发不变）。
- 下游：服务端 **PUB 绑定** `tcp://127.0.0.1:5557`（`SangoSeamConfig.DetectionEndpoint`；localhost only）；Unity 侧 SUB connect + `subscribe("sango.detection")`（`SangoSeamConfig.DetectionTopic`）。
- 高水位两侧 30（消费端掉线不积压，与发布端对称）。
- Unity 侧库：NetMQ 4.0.1.13 同 frame-publisher-v1 §1（三 dll 同目录，未新增依赖）。

## 2. 消息（multipart ×2）

| 段 | 内容 | 校验 |
|---|---|---|
| 1 | topic，恒 `"sango.detection"`（UTF-8） | SUB 过滤键 |
| 2 | `DetectionResult` JSON（UTF-8，compact） | detection-result-v1.md §2 schema |

```json
{"frame_seq":17,"frame_time_s":3.402,"source":"yolo-detector","detections":[{"box_xyxy":[120.5,88.0,412.25,301.5],"class_id":8,"class_name":"boat","confidence":0.634}]}
```

- `frame_seq` / `frame_time_s` 逐帧透传上游 FrameMetadata，Unity 侧不重算。
- **每进入推理的一帧恰发一条结果（推理前排空积压取最新帧，跳号容忍）**，含零检测帧（`detections:[]` = YOLO 权威"没看到"）。
- 框坐标即原图像素（服务端对解码后原始分辨率推理，box 无缩放偏移），与 FrameMetadata width/height 同域。
- 类映射：COCO `boat`（id=8）过滤保留；`class_name` 取模型 names 表映射（yolov8n → `"boat"`）。演进只加不减（未知字段 JsonUtility 忽略）。

## 3. 新鲜度规则（消费端）

- **age = Unity 本地 `Time.timeAsDouble` − `result.frame_time_s`**，只认 `0 ≤ age ≤ 0.5s`（`DetectionFreshness.MaxAgeS`）。帧时间源自同一 Unity 实例时钟（发布端 `Time.timeAsDouble`），钟域一致；负 age（未来戳，时钟域不一致的外部源）按陈旧拒绝。
- **seq 连续**：只消费 `frame_seq` 严格大于上一已消费结果的结果（跳号容忍，重复/乱序拒绝；初始 lastSeq=−1）。
- **渲染判定**（`DetectionFreshness.PreferLiveOverGroundTruth`）：有新鲜 live 结果 → live 路径按 `box_xyxy` 像素直绘（标签 = `class_name + confidence` 两位小数）；**新鲜空结果也是 live 接管**（渲染零框）；无新消息时保留最近的新鲜结果至窗口到期；null/畸形/陈旧 → 回退 ground-truth（M3 行为逐位不变，B 键行为不变）。
- 逐帧排空取最大有效 seq：消费端队列只保留最新结果（`TryTakeFresh`），推理落后发布节奏时旧结果自然被淘汰进回退。

## 4. 开关与零成本

- **CLI 旗标 `--sango-publisher` 为 seam 总闸**（`SangoSeamConfig.ConsumerCliFlag == PublisherCliFlag`）：同时使能 FramePublisher 与 DetectionResultConsumer，一处开闸两侧同使能。
- 消费端编译期恒关（`runtimeEnabled` 默认 false）；关闸成本：零 socket、零线程、零队列，`Update` 仅布尔比较、`TryTakeFresh` 一次布尔早退（先例 FramePublisher 验收故事 5）。
- 等价启用路径：Inspector 勾 `runtimeEnabled` 或运行时调 `StartConsumer()`。

  ```bash
  # 1) pkill -f 'MacOS/sango'（先清旧实例）
  # 2) 服务端（另一终端亦可）
  .venv-detector/bin/python tools/sango_detector_service.py
  # 3) 带总闸启动 M1 玩家构建（场景需挂 DetectionResultConsumer 组件）
  ./sango/Builds/sango.app/Contents/MacOS/sango --sango-publisher
  # 4) B 键开 overlay：有 YOLO 结果显示 "boat 0.63" 式框，服务停跑后 0.5s 内回退真值框
  ```

## 5. 服务端（tools/sango_detector_service.py）

- 依赖：仓库根 `.venv-detector`（`python3 -m venv` + `pip install pyzmq ultralytics`）；权重 `models/yolov8n.pt`（ultralytics 首跑自动下载到该路径）。
- 默认：yolov8n、conf≥0.25、COCO boat(id=8)、source=`"yolo-detector"`；`--model/--conf/--endpoint/--out/--topic/--out-topic/--source/--device/--log-every` 参数化。
- 日志：每 `--log-every`（默认 10）帧打一行 `[detector] rx=N tx=M seq=… infer=…ms detections=…`；Ctrl-C 打 shutdown 总计。
- 自检：`--selftest` 对一张程序合成图直接跑模型（零 socket），验证依赖 + 权重，exit 0 即通过。

## 6. 无 Unity 联调（tools/sango_detector_replay.py）

- 把一张 JPEG 按 `--fps`（默认 5）重发到 `tcp://127.0.0.1:5556`，元数据同 FrameMetadata 契约（width/height/jpeg_bytes 取实际文件，source=`"replay"`）。
- `frame_time_s` = 重放进程单调钟（非 Unity 时钟）——**新鲜度语义仅对 Unity 真源成立**，replay 仅供 Python 侧链路联调，不建议接 Unity 消费端。
- 与 FramePublisher 互斥（同一端点 bind，不可同时跑）。

## 7. 已知边界

- DetectionResultConsumer 的 SUB 在后台线程（NetMQ socket 单线程属主）；停止 Join 上限 1s（recv 200ms tick），极端情况线程滞后由告警暴露。
- 服务端推理速率低于发布速率时，结果天然落后 → 新鲜度窗按设计回退真值（不阻塞、不积压：HWM 30 + 逐帧排空）。
- overlay 自动接线只在组件首帧查找一次（`FindFirstObjectByType`）；后加的 consumer 组件需 Inspector 显式引用或重启 Play。
