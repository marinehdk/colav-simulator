"""observations-v1 契约测试（P3-S0，spec #90）。

冻结字面量 = ``sango/Docs/contracts/observations-v1.md`` §7 样例（同源对拍）。
仅 schema 校验——路由/会话闸/单调性存储是 S2 实现面（gui_server 本段零改动）。
检测框字段面 = detection-result-v1 §2 ``detections[]`` 逐字段子集（上游 ZMQ
payload 无需改形即可转发），样例数值沿用该契约 §2 船样例。
"""

import pytest
from pydantic import ValidationError

from colav_simulator.schemas.observations_v1 import (
    OBSERVATION_SENSOR_IDS,
    ObservationAccepted,
    ObservationFrame,
    PixelDetection,
)

# ── 契约 §7 冻结样例字面量（文档同源；勿改值，改则三处同步） ──────────────────

OBSERVATION_REQUEST_SAMPLE = (
    '{"schema_version":"observations@1","frame_seq":41,"frame_time_s":12.402,'
    '"sensor_id":2,"mount_id":"mast_eo_bow","source":"yolo-detector",'
    '"detections":[{"box_xyxy":[100.0,120.0,340.0,260.0],"class_id":8,'
    '"class_name":"boat","confidence":0.87}]}'
)

OBSERVATION_EMPTY_SAMPLE = (
    '{"schema_version":"observations@1","frame_seq":42,"frame_time_s":13.502,'
    '"sensor_id":3,"mount_id":"mast_ir_bow","detections":[]}'
)

OBSERVATION_ACCEPTED_SAMPLE = '{"accepted":true,"frame_seq":41,"detections_accepted":1}'


def test_request_sample_deserializes_to_documented_fields() -> None:
    frame = ObservationFrame.model_validate_json(OBSERVATION_REQUEST_SAMPLE)
    assert frame.schema_version == "observations@1"
    assert frame.frame_seq == 41
    assert frame.frame_time_s == pytest.approx(12.402)
    assert frame.sensor_id == 2  # camera_eo
    assert frame.mount_id == "mast_eo_bow"
    assert frame.source == "yolo-detector"
    assert len(frame.detections) == 1
    detection = frame.detections[0]
    assert detection.box_xyxy == pytest.approx([100.0, 120.0, 340.0, 260.0])
    assert detection.class_id == 8
    assert detection.class_name == "boat"
    assert detection.confidence == pytest.approx(0.87)


def test_detection_fields_are_a_detection_result_v1_subset() -> None:
    # detection-result-v1 §2 样例 payload（YOLO 服务 → Unity 的既有 ZMQ 形状）逐字段
    # 嵌入本契约请求体：上游转发零改形的证据。
    upstream_detection = {"box_xyxy": [120.5, 88.0, 412.25, 301.5], "class_id": 8, "class_name": "boat", "confidence": 0.634}
    frame = ObservationFrame(
        schema_version="observations@1",
        frame_seq=17,
        frame_time_s=3.402,
        sensor_id=2,
        mount_id="mast_eo_bow",
        detections=[PixelDetection(**upstream_detection)],
    )
    assert frame.detections[0].box_xyxy == pytest.approx([120.5, 88.0, 412.25, 301.5])


def test_empty_detections_is_authoritative_no_see() -> None:
    # 沿 detection-return-v1 §2：detections:[] = YOLO 权威"没看到"（非无效消息）。
    frame = ObservationFrame.model_validate_json(OBSERVATION_EMPTY_SAMPLE)
    assert frame.sensor_id == 3  # camera_ir
    assert frame.detections == []


def test_request_roundtrip_json_stable() -> None:
    frame = ObservationFrame.model_validate_json(OBSERVATION_REQUEST_SAMPLE)
    reparsed = ObservationFrame.model_validate_json(frame.model_dump_json())
    assert reparsed == frame


@pytest.mark.parametrize(
    "mutation",
    [
        lambda doc: doc.replace('"sensor_id":2', '"sensor_id":1'),  # 雷达不经本端点
        lambda doc: doc.replace('"sensor_id":2', '"sensor_id":4'),  # LiDAR 旁路不经本端点
        lambda doc: doc.replace('"sensor_id":2', '"sensor_id":5'),  # AIS 不经本端点
        lambda doc: doc.replace('"schema_version":"observations@1"', '"schema_version":"observations@2"'),
        lambda doc: doc.replace('"mount_id":"mast_eo_bow"', '"mount_id":""'),
        lambda doc: doc.replace('"mount_id":"mast_eo_bow",', ""),
        lambda doc: doc.replace('"frame_seq":41', '"frame_seq":-1'),
        lambda doc: doc.replace('"confidence":0.87', '"confidence":1.2'),
        lambda doc: doc.replace('"box_xyxy":[100.0,120.0,340.0,260.0]', '"box_xyxy":[100.0,120.0,340.0]'),
        lambda doc: doc.replace('"class_id":8', '"class_id":-3'),
        lambda doc: doc.replace('"source":"yolo-detector"', '"source":"yolo-detector","georef":[[1.0,2.0]]'),
    ],
)
def test_request_sample_rejects_contract_violations(mutation) -> None:
    assert mutation(OBSERVATION_REQUEST_SAMPLE) != OBSERVATION_REQUEST_SAMPLE
    with pytest.raises(ValidationError):
        ObservationFrame.model_validate_json(mutation(OBSERVATION_REQUEST_SAMPLE))


def test_degenerate_boxes_rejected_by_shape_not_vocabulary() -> None:
    with pytest.raises(ValidationError):
        PixelDetection(box_xyxy=[100.0, 120.0, 100.0, 260.0], class_id=8, class_name="boat", confidence=0.9)
    with pytest.raises(ValidationError):
        PixelDetection(box_xyxy=[-1.0, 120.0, 340.0, 260.0], class_id=8, class_name="boat", confidence=0.9)


def test_sensor_vocabulary_is_camera_chain_only() -> None:
    assert OBSERVATION_SENSOR_IDS == (2, 3)


def test_accepted_response_sample_deserializes() -> None:
    accepted = ObservationAccepted.model_validate_json(OBSERVATION_ACCEPTED_SAMPLE)
    assert accepted.accepted is True
    assert accepted.frame_seq == 41
    assert accepted.detections_accepted == 1
    with pytest.raises(ValidationError):
        ObservationAccepted.model_validate_json('{"accepted":false,"frame_seq":1,"detections_accepted":0}')
