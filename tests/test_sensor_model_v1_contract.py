"""sensor-model-v1 契约测试（P3-S0，spec #90）。

冻结字面量 = ``sango/Docs/contracts/sensor-model-v1.md`` §7 样例（同源对拍：
文档样例、本文件、契约文档三者字面量一致）。fixture 数值为真实形状样例：
VIMM 标定噪声/可见性/杂波/阈值来自 milliAmpere autoferry 标定链
（``docs/research/2026-09-30-mass-situational-awareness/04-multi-sensor-fusion-ipda.md``
§2.5，经 ``milliampere-ch5-fcb45-layout.md`` §6 转正）；坐标样例量级对齐仓库
NE 米制（北东序，state=[N, E, vN, vE] 惯例）。本文件仅 schema 校验——端点/生成器
实现属 S2/S5（零运行时行为变化）。
"""

import math

import pytest
from pydantic import ValidationError

from colav_simulator.schemas.sensor_model_v1 import (
    FUSION_SENSOR_IDS,
    SENSOR_LABELS,
    TRACK_ADDITIVE_FIELDS,
    ConfirmedTrack,
    ConfirmedTrackList,
    SfdGeneratorConfig,
    SfdMeasurement,
    SfdMeasurementFrame,
    SensorId,
    TracksSnapshotV1,
)

# ── 契约 §7 冻结样例字面量（文档同源；勿改值，改则三处同步） ──────────────────

RADAR_FRAME_SAMPLE = (
    '{"schema_version":"sensor-model@1","frame_id":"ownship_ned","t_s":12.4,'
    '"sensor_id":1,"sensor_label":"radar_x","mount_id":"mast_top_xband",'
    '"measurements":[{"sensor_id":1,"target_hint":null,"position_ne_m":[1520.5,-310.25],'
    '"position_cov_ne_m2":[[64.0,0.0],[0.0,64.0]],"t_s":12.4,"confidence":0.92,'
    '"class_name":null,"class_confidence":null}],'
    '"ownship_pose_at_measurement":{"p_n":6955012.25,"p_e":37012.5,"yaw":1.5708,'
    '"pitch":0.0,"roll":0.0},"epoch_unix_ns":null}'
)

CAMERA_IR_FRAME_SAMPLE = (
    '{"schema_version":"sensor-model@1","frame_id":"ownship_ned","t_s":13.1,'
    '"sensor_id":3,"sensor_label":"camera_ir","mount_id":"mast_ir_bow",'
    '"measurements":[{"sensor_id":3,"target_hint":null,"position_ne_m":[620.75,95.5],'
    '"position_cov_ne_m2":[[36.0,0.0],[0.0,121.0]],"t_s":13.1,"confidence":0.71,'
    '"class_name":"ship","class_confidence":0.83}],'
    '"ownship_pose_at_measurement":{"p_n":6955012.25,"p_e":37012.5,"yaw":1.5708},'
    '"epoch_unix_ns":1738368000000000000}'
)

AIS_BYPASS_FRAME_SAMPLE = (
    '{"schema_version":"sensor-model@1","frame_id":"ownship_ned","t_s":14.0,'
    '"sensor_id":5,"sensor_label":"ais","mount_id":"mast_vdl",'
    '"measurements":[{"sensor_id":5,"target_hint":2,"position_ne_m":[900.0,-40.0],'
    '"position_cov_ne_m2":[[25.0,0.0],[0.0,25.0]],"t_s":13.6,"confidence":1.0,'
    '"class_name":null,"class_confidence":null}],'
    '"ownship_pose_at_measurement":{"p_n":6955012.25,"p_e":37012.5,"yaw":1.5708},'
    '"epoch_unix_ns":null}'
)

CONFIRMED_TRACKS_SAMPLE = (
    '{"schema_version":"sensor-model@1/tracks","t_s":14.0,"tracks":['
    '{"track_key":"7:1","target_id":7,"generation":1,"existence_prob":0.997,'
    '"quality":0.88,"sources":[{"sensor_id":1,"last_seen_age_s":0.4},'
    '{"sensor_id":5,"last_seen_age_s":1.2}],"position_ne_m":[1520.5,-310.25],'
    '"velocity_ne_mps":[-6.2,0.3],"heading_rad":3.124,'
    '"position_cov_ne_m2":[[49.0,0.0],[0.0,49.0]],"class_name":"ship",'
    '"class_confidence":0.83}]}'
)

# 契约 §6：WS 全量 1.0 transport truth[].tracks + P3 加性字段（同一字面量在
# gui_server _local_tracks 形状对拍；文档 §6 与本文件同源）。
TRACKS_SNAPSHOT_SAMPLE = (
    '{"labels":[7],"generations":[1],"states":[[1520.5,-310.25,-6.2,0.3]],'
    '"covariances":[[[49.0,0.0],[0.0,49.0]]],"nis":[2.31],"existence_prob":[0.997],'
    '"quality":[0.88],"sources":[[{"sensor_id":1,"last_seen_age_s":0.4},'
    '{"sensor_id":5,"last_seen_age_s":1.2}]]}'
)

# 旧发布端形状（无 P3 字段）必须继续合法——加性演进零破坏的证据。
TRACKS_SNAPSHOT_LEGACY_SAMPLE = (
    '{"labels":[7],"generations":[1],"states":[[1520.5,-310.25,-6.2,0.3]],'
    '"covariances":[[[49.0,0.0],[0.0,49.0]]],"nis":[2.31]}'
)


# ── sensorID 词汇（契约 §2） ──────────────────────────────────────────────────


def test_sensor_id_vocabulary_is_frozen_renumbering() -> None:
    assert [int(s) for s in SensorId] == [1, 2, 3, 4, 5]
    assert SENSOR_LABELS == {
        1: "radar_x",
        2: "camera_eo",
        3: "camera_ir",
        4: "lidar",
        5: "ais",
    }
    # 铁律：LiDAR/AIS 旁路不进融合器（00-PLAN §3；报告 04 开放问题 5）。
    assert FUSION_SENSOR_IDS == {SensorId.RADAR_X, SensorId.CAMERA_EO, SensorId.CAMERA_IR}


# ── 量测流消息（契约 §3/§7 样例反序列化） ─────────────────────────────────────


def test_radar_frame_sample_deserializes_to_documented_fields() -> None:
    frame = SfdMeasurementFrame.model_validate_json(RADAR_FRAME_SAMPLE)
    assert frame.schema_version == "sensor-model@1"
    assert frame.frame_id == "ownship_ned"
    assert frame.t_s == pytest.approx(12.4)
    assert frame.sensor_id is SensorId.RADAR_X
    assert frame.sensor_label == "radar_x"
    assert frame.mount_id == "mast_top_xband"
    assert len(frame.measurements) == 1
    measurement = frame.measurements[0]
    assert measurement.position_ne_m == pytest.approx([1520.5, -310.25])
    assert measurement.position_cov_ne_m2[0] == pytest.approx([64.0, 0.0])
    assert measurement.position_cov_ne_m2[1] == pytest.approx([0.0, 64.0])
    assert measurement.confidence == pytest.approx(0.92)
    assert measurement.target_hint is None
    assert measurement.class_name is None
    assert frame.ownship_pose_at_measurement.p_n == pytest.approx(6955012.25)
    assert frame.ownship_pose_at_measurement.yaw == pytest.approx(1.5708)
    assert frame.epoch_unix_ns is None


def test_camera_ir_frame_sample_carries_class_and_georeferenced_ne() -> None:
    frame = SfdMeasurementFrame.model_validate_json(CAMERA_IR_FRAME_SAMPLE)
    assert frame.sensor_id is SensorId.CAMERA_IR
    measurement = frame.measurements[0]
    # georef 已由生成器完成：进 SFD 的相机量测是 NE（契约 §3 注）。
    assert measurement.position_ne_m == pytest.approx([620.75, 95.5])
    # 径向拉长协方差（报告 04 E5 形态：北向 σ=6m，东向 σ=11m 样例）。
    assert measurement.position_cov_ne_m2[0][0] == pytest.approx(36.0)
    assert measurement.position_cov_ne_m2[1][1] == pytest.approx(121.0)
    assert measurement.class_name == "ship"
    assert measurement.class_confidence == pytest.approx(0.83)
    assert frame.epoch_unix_ns == 1738368000000000000


def test_ais_bypass_frame_sample_keeps_target_hint() -> None:
    frame = SfdMeasurementFrame.model_validate_json(AIS_BYPASS_FRAME_SAMPLE)
    assert frame.sensor_id is SensorId.AIS
    measurement = frame.measurements[0]
    assert measurement.target_hint == 2, "AIS mmsi→do_idx 映射落在 target_hint（生成器边界）"
    assert measurement.t_s == pytest.approx(13.6), "报文接收时戳可早于帧 t_s（龄期语义）"


def test_measurement_frame_roundtrip_json_stable() -> None:
    frame = SfdMeasurementFrame.model_validate_json(RADAR_FRAME_SAMPLE)
    reparsed = SfdMeasurementFrame.model_validate_json(frame.model_dump_json())
    assert reparsed == frame


@pytest.mark.parametrize(
    "mutation",
    [
        lambda doc: doc.replace('"sensor_label":"radar_x"', '"sensor_label":"camera_eo"'),
        lambda doc: doc.replace('"sensor_id":1,"target_hint"', '"sensor_id":3,"target_hint"'),
        lambda doc: doc.replace('"schema_version":"sensor-model@1"', '"schema_version":"sensor-model@2"'),
        lambda doc: doc.replace('"frame_id":"ownship_ned"', '"frame_id":"world_utm"'),
        lambda doc: doc.replace('"confidence":0.92', '"confidence":1.5'),
        lambda doc: doc.replace('"t_s":12.4,"confidence"', '"t_s":12.4,"extra_field":1,"confidence"'),
    ],
)
def test_radar_frame_sample_rejects_contract_violations(mutation) -> None:
    assert mutation(RADAR_FRAME_SAMPLE) != RADAR_FRAME_SAMPLE
    with pytest.raises(ValidationError):
        SfdMeasurementFrame.model_validate_json(mutation(RADAR_FRAME_SAMPLE))


def test_measurement_rejects_asymmetric_or_negative_covariance() -> None:
    base = {
        "sensor_id": SensorId.RADAR_X,
        "position_ne_m": [10.0, 0.0],
        "t_s": 1.0,
        "confidence": 0.9,
    }
    with pytest.raises(ValidationError):
        SfdMeasurement(**base, position_cov_ne_m2=[[4.0, 0.5], [0.0, 4.0]])
    with pytest.raises(ValidationError):
        SfdMeasurement(**base, position_cov_ne_m2=[[-4.0, 0.0], [0.0, 4.0]])
    with pytest.raises(ValidationError):
        SfdMeasurement(**base, position_cov_ne_m2=[[4.0, 0.0]])
    with pytest.raises(ValidationError):
        SfdMeasurement(**base, position_cov_ne_m2=[[4.0, 0.0], [0.0, 4.0]], class_confidence=0.5)


# ── 退化参数包（契约 §4：默认值 = VIMM 标定锚） ───────────────────────────────


def test_generator_config_defaults_are_vimm_calibrated() -> None:
    config = SfdGeneratorConfig()
    assert config.noise.lidar_sigma_c_m == pytest.approx(6.6)
    assert config.noise.radar_sigma_r_m == pytest.approx(8.0)
    assert config.noise.radar_sigma_theta_rad == pytest.approx(math.radians(1.0))
    assert config.visibility.w11 == pytest.approx(0.90)
    assert config.visibility.w01 == pytest.approx(0.52)
    assert config.visibility.global_pd == pytest.approx(0.92)
    assert config.visibility.fov_outside_pd == pytest.approx(0.0)
    assert config.clutter.poisson_rate_per_m2 == pytest.approx(5e-7)
    assert config.clutter.new_target_rate_per_m2 == pytest.approx(1e-7)
    assert config.async_jitter.radar_scan_period_s == pytest.approx(2.5)
    assert config.track_mgmt.confirm_threshold == pytest.approx(0.999)
    assert config.track_mgmt.delete_threshold == pytest.approx(0.01)
    assert config.track_mgmt.terminate_after == 6


def test_generator_config_rejects_unknown_fields_and_bad_rpm_gear() -> None:
    with pytest.raises(ValidationError):
        SfdGeneratorConfig.model_validate({"unknown": True})
    with pytest.raises(ValidationError):
        SfdGeneratorConfig.model_validate({"async_jitter": {"radar_scan_period_s": 1.7}})


# ── 确认航迹输出（契约 §5/§7） ────────────────────────────────────────────────


def test_confirmed_tracks_sample_deserializes_to_documented_fields() -> None:
    parsed = ConfirmedTrackList.model_validate_json(CONFIRMED_TRACKS_SAMPLE)
    assert parsed.schema_version == "sensor-model@1/tracks"
    assert len(parsed.tracks) == 1
    track = parsed.tracks[0]
    assert track.track_key == "7:1"
    assert track.existence_prob == pytest.approx(0.997)
    assert track.quality == pytest.approx(0.88)
    assert [source.sensor_id for source in track.sources] == [SensorId.RADAR_X, SensorId.AIS]
    assert track.class_name == "ship"
    assert track.class_confidence == pytest.approx(0.83)


def test_confirmed_track_rejects_out_of_range_existence_probability() -> None:
    with pytest.raises(ValidationError):
        ConfirmedTrackList.model_validate_json(CONFIRMED_TRACKS_SAMPLE.replace("0.997", "1.5"))


def test_confirmed_track_rejects_class_confidence_without_class_name() -> None:
    payload = {
        "schema_version": "sensor-model@1/tracks",
        "t_s": 1.0,
        "track_key": "1:1",
        "target_id": 1,
        "generation": 1,
        "existence_prob": 0.99,
        "quality": 0.5,
        "sources": [{"sensor_id": 1}],
        "position_ne_m": [0.0, 0.0],
        "velocity_ne_mps": [0.0, 0.0],
        "heading_rad": 0.0,
        "position_cov_ne_m2": [[1.0, 0.0], [0.0, 1.0]],
        "class_confidence": 0.9,
    }
    with pytest.raises(ValidationError):
        ConfirmedTrack(**payload)


# ── WS tracks 加性置信度字段（契约 §6，D 交付） ───────────────────────────────


def test_tracks_snapshot_sample_deserializes_with_additive_fields() -> None:
    tracks = TracksSnapshotV1.model_validate_json(TRACKS_SNAPSHOT_SAMPLE)
    assert tracks.labels == [7]
    assert tracks.existence_prob == pytest.approx([0.997])
    assert tracks.quality == pytest.approx([0.88])
    assert tracks.sources is not None
    assert [source.sensor_id for source in tracks.sources[0]] == [SensorId.RADAR_X, SensorId.AIS]


def test_tracks_snapshot_legacy_payload_without_additive_fields_is_valid() -> None:
    tracks = TracksSnapshotV1.model_validate_json(TRACKS_SNAPSHOT_LEGACY_SAMPLE)
    assert tracks.existence_prob is None
    assert tracks.quality is None
    assert tracks.sources is None
    assert TRACK_ADDITIVE_FIELDS == ("existence_prob", "quality", "sources")


def test_tracks_snapshot_rejects_ragged_parallel_arrays() -> None:
    ragged = TRACKS_SNAPSHOT_SAMPLE.replace('"existence_prob":[0.997]', '"existence_prob":[0.997,0.1]')
    with pytest.raises(ValidationError):
        TracksSnapshotV1.model_validate_json(ragged)
    with pytest.raises(ValidationError):
        TracksSnapshotV1.model_validate({"labels": [7], "generations": [1, 2]})
