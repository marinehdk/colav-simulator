# detection-result-v1 — 检测框回传契约（M3 缝钉子④，spec #86）

状态：**已冻结**（2026-09-28，M3）。方向：**检测宿主 → Unity**（叠加显示）。
C# 镜像：`sango/Assets/Scripts/Runtime/Vessels/DetectionResult.cs`（JsonUtility 兼容，plain serializable）。
回环测试：`Assets/Scripts/Tests/EditMode/DetectionResultRoundTripTests.cs`（serialize→deserialize→serialize 字符串逐位无损 + 字段断言，钉死本文档 §2 示例字面量）。

## 1. 语义

一帧画面的检测框集合。phase-1 由 Unity 自产真值（`DetectionOverlay.ProvideGroundTruth()`，confidence 恒 1，source=`"ground-truth"`）；phase-2 换 a4000 YOLO 服务输出（source=`"yolo-a4000"` 式标识），渲染路径零改动（`DetectionOverlay` 来源无关）。

框坐标：`box_xyxy = [x0, y0, x1, y1]`，**像素坐标、原点画面左上、y 向下**（视觉惯例，与 `FrameMetadata` 的 width/height 同帧同域）。`frame_seq` 与发布帧的 `FrameMetadata.frame_seq` 对齐。

## 2. Schema（JSON，UTF-8）

```json
{
  "frame_seq": 41,
  "frame_time_s": 12.5,
  "source": "yolo-a4000",
  "detections": [
    {
      "box_xyxy": [100.0, 120.0, 340.0, 260.0],
      "class_id": 1,
      "class_name": "ship",
      "confidence": 0.87
    }
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `frame_seq` | int | 是 | 来源帧号（FrameMetadata.frame_seq） |
| `frame_time_s` | double | 是 | 来源帧发布时刻（秒） |
| `source` | string | 是 | 检测源标识（`"ground-truth"` / `"yolo-a4000"` / …） |
| `detections` | array | 是（可为空数组） | 检测框列表 |
| `detections[].box_xyxy` | float[4] | 是 | `[x0,y0,x1,y1]` 像素，左上原点 y 向下 |
| `detections[].class_id` | int | 是 | 类别索引 |
| `detections[].class_name` | string | 是 | 类别名（演示用 `"ship"`） |
| `detections[].confidence` | float | 是 | [0,1]；真值恒 1，标签渲染为 `1.0 (gt)` |

未知字段一律忽略（JsonUtility 语义）；缺字段取类型默认值——**向后兼容只加不减**。

## 3. 通道选型（PLAN §8.8）

- **默认**：Unity 侧 ZeroMQ SUB ↔ a4000 YOLO 服务 PUB/推（与 FramePublisher 对称、后端 Colav 零改动）。
- **备选**：检测框需进 Colav tracker（非仅叠加）→ 阶段3 `POST /api/sessions/{id}/observations` 注入端点（当前后端不存在该端点，04 文档 B.2 核实；需后端新增，不在"零改动"范围）。
- 本里程碑不激活任何通道（spec Out of Scope）；契约与测试即交付物。
