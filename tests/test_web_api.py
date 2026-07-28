from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from colav_simulator.experiment import ExperimentRunner, RunSpec
from gui_server.main import app


def test_header_uses_requested_session_labels() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/app.js")
        assert page.status_code == 200
        assert script.status_code == 200
        assert "<h1>综合避碰仿真器</h1>" in page.text
        assert "Autonomous Ship COLAV" not in page.text
        assert (
            '<span id="conn-status">会话: 断连</span>' in page.text
            and page.text.index('class="header-run-info"')
            < page.text.index('id="conn-status"')
            < page.text.index("<main")
            and all(label in page.text for label in ("北京时间", "仿真时间", 'id="val-beijing-time"'))
            and 'id="val-step"' not in page.text
            and 'id="val-algo-active"' not in page.text
        )
        assert "canvas-overlay-info" not in page.text
        assert "ecosystem-tags" not in page.text
        tab_labels = ["Rule 13-OT", "Rule 14-HO", "Rule 15-CS", "多船情形"]
        assert [page.text.index(label) for label in tab_labels] == sorted(page.text.index(label) for label in tab_labels)
        assert page.text.index('id="scenarioSelect"') > page.text.index("<main")
        assert 'class="insights-column"' in page.text
        assert 'data-group="rule14"' in page.text
        assert "快速场景切换" not in page.text
        assert page.text.index('id="canvasWrapper"') < page.text.index('id="toggleENC"')
        assert page.text.index('id="canvasWrapper"') < page.text.index('id="logTerminal"')
        assert (
            'aria-label="仿真事件"' in page.text
            and 'id="cardEvents"' in page.text
            and 'id="logToggle"' not in page.text
            and 'class="log-section map-log-overlay card glass-card"' in page.text
        )
        assert "仿真器事件" not in page.text
        assert "仿真事件日志" not in page.text
        assert "[--:--:--] System ready." in page.text
        assert page.text.index('id="scaleBar"') < page.text.index('id="zoomIn"')
        assert page.text.index('id="canvasWrapper"') < page.text.index('data-speed="10.0"')
        assert 'class="compass-wrapper"' not in page.text
        assert "下发启动命令" in page.text
        assert 'class="bottom-console' not in page.text
        assert 'id="cardEvidence"' not in page.text
        assert "<summary>图标说明</summary>" in page.text
        assert "<summary>航行展示</summary>" in page.text
        assert "电子海图 ENC Live View" not in page.text
        assert 'id="encChartSelect"' in page.text
        assert ">Romsdal</option>" in page.text
        assert ">Rogaland</option>" in page.text
        assert '<span class="enc-status-badge" id="encStatusBadge">加载中</span>' in page.text
        assert "生态库标签" not in page.text
        assert "仿真与算法控制" not in page.text
        assert all(
            label in page.text
            for label in (
                "系统安装插件",
                "避碰测试规则",
                "避碰规划算法",
                "目标跟踪器",
                "避碰安全指标",
                ">DCPA<",
                ">TCPA<",
                    "COLREGs规则",
                    "本船遥测状态",
                    ">经纬度<",
                    ">对地速度<",
                    ">对地航向<",
                    ">当前航向<",
                    ">角速度<",
                    "算法性能监控",
                )
        ) and all(
            label not in page.text
            for label in (
                "对应COLREGs规则",
                "MPC 预测时域 (Horizon)",
                "求解耗时",
                "迭代次数",
                "目标函数",
                "候选数量",
                "遭遇阶段",
                "算法数据",
                ">约束<",
                "(Performance)",
            )
        )
        module_ids = ['id="cardIntegrations"', 'id="cardRules"', 'id="cardControl"', 'id="cardTracker"']
        assert [page.text.index(module_id) for module_id in module_ids] == sorted(
            page.text.index(module_id) for module_id in module_ids
        )
        assert all(token in page.text for token in ('id="scenarioCatalog"', "追越与被追越", "对遇避碰"))
        assert 'data-algorithm="sbmpc"' in page.text
        assert 'data-algorithm="vo"' in page.text
        assert 'class="algorithm-catalog"' in page.text
        assert '<option value="sbmpc" selected>内置 SB-MPC</option>' in page.text
        assert 'class="selection-card selected" type="button" data-algorithm="sbmpc"' in page.text
        assert 'data-tracker="vimmjipda"' in page.text
        assert '<option value="god" selected>God Tracker</option>' in page.text
        assert "标准对遇 · G3 · 300s" in page.text
        assert "概率安全域 MPC 避碰" in page.text
        assert "ENC 高层路径规划" in page.text
        assert "雷达多目标跟踪" in page.text
        assert 'id="cardPlanner"' in page.text
        assert 'id="val-solver-executed"' in page.text
        assert 'id="solveTimeline"' in page.text
        assert 'id="objectiveHistory"' in page.text
        assert 'id="objectiveHistoryWrap"' in page.text
        assert "候选控制代价" in page.text
        assert "求解周期" in page.text
        assert all(
            f'id="{metric_id}"' in page.text
            for metric_id in (
                "val-best-cost",
                "val-best-course-offset",
                "val-best-speed-scale",
                "val-solve-period",
            )
        )
        assert 'id="val-surface-summary"' not in page.text
        assert "VO / COLREGS 候选速度可行性" in script.text
        assert "details.heading_offsets_rad" in script.text
        assert "details.speed_offsets_mps" in script.text
        assert "objectiveHistoryWrap.hidden = algorithmId !== 'sbmpc'" in script.text


def test_chart_layer_controls_follow_navigation_semantics() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/app.js")
        assert page.status_code == 200
        assert script.status_code == 200
        assert all(
            f'data-layer="{layer}"' in page.text
            for layer in (
                "safeWater",
                "ships",
                "corridor",
                "route",
                "waypoints",
                "history",
                "motionVectors",
                "radarRange",
                "responseRange",
                "prediction",
                "previousPrediction",
                "executionPoint",
                "risk",
                "truth",
                "measurements",
                "tracks",
                "covariance",
            )
        )
        assert 'data-layer="truth" checked' not in page.text
        assert 'data-layer="measurements" checked' not in page.text
        assert 'data-layer="previousPrediction" checked' not in page.text
        assert 'id="targetDetails"' in page.text
        assert all(label in page.text for label in ("安全海域", "初始航道", "60s 向量"))
        assert all(
            token in script.text
            for token in (
                "const FCB45_LENGTH_M = 45",
                "const FCB45_WIDTH_M = 8",
                "const PREDICTION_MARKER_SECONDS = 10",
                "const PREDICTION_LABEL_SECONDS = 60",
                "const SBMPC_SOLVE_PERIOD_SECONDS = 5",
                "new Path2D()",
                "threat_level || 'UNKNOWN'",
                "own_cpa_position",
                "target_cpa_position",
                "activation_distance_m",
                "RADAR_DETECTION_RANGE_M = 2000",
                "SBMPC_RESPONSE_RANGE_M = 1000",
                "distance <= RADAR_DETECTION_RANGE_M",
                "seenEventKeys",
                "求解成功",
                "仿真 ${simTime.toFixed(1)}s",
            )
        )
        assert "SB-MPC 激活/安全范围" not in page.text
        assert all(label in page.text for label in ("雷达探测圈（2 km）", "避碰响应圈（1 km）"))
        assert all(label in page.text for label in ("经纬度", "对地速度", "对地航向", "当前航向", "角速度"))
        assert all(
            legacy_label not in page.text
            for legacy_label in ("北向坐标", "东向坐标", "北向速度", "东向速度")
        )


def test_real_session_api_and_websocket() -> None:
    with TestClient(app) as client:
        scenarios = client.get("/api/scenarios")
        assert scenarios.status_code == 200
        assert any(item["id"] == "paper_ccta2023_multiship" for item in scenarios.json())

        created = client.post(
            "/api/sessions",
            json={"scenario_id": "paper_ccta2023_multiship", "t_end": 0.2},
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        navigation = client.get(f"/api/sessions/{session_id}/navigation-area")
        assert navigation.status_code == 200
        navigation_area = navigation.json()
        assert navigation_area["coordinate_frame"] == "local_north_east_m"
        assert navigation_area["minimum_depth_m"] >= navigation_area["vessel_draft_m"]
        assert navigation_area["safe_water"]["type"] == "MultiPolygon"
        assert navigation_area["safe_water"]["polygons"]

        first = client.post(f"/api/sessions/{session_id}/step")
        assert first.status_code == 200
        assert first.json()["state"] == "PAUSED"
        assert first.json()["schema_version"] == "1.0"
        assert len(first.json()["obstacles"]) == 3
        assert len(first.json()["truth"]) == 4
        assert first.json()["measurements"] is not None
        assert first.json()["tracks"] is not None
        assert first.json()["tracks"][0]["states"][0][0] < 5000.0
        assert first.json()["enc_navigation_area"] == navigation_area
        assert -90.0 <= first.json()["os"]["latitude"] <= 90.0
        assert -180.0 <= first.json()["os"]["longitude"] <= 180.0

        second = client.post(f"/api/sessions/{session_id}/step")
        assert second.status_code == 200
        assert second.json()["state"] == "FINISHED"

        result = client.get(f"/api/sessions/{session_id}/result")
        assert result.status_code == 200
        assert result.json()["manifest"]["reproduction_status"] == "functional_reproduction"

        artifacts = client.get(f"/api/sessions/{session_id}/artifacts")
        names = {artifact["name"] for artifact in artifacts.json()}
        assert {"enc.png", "manifest.json", "trajectory.parquet", "evaluation.json", "report.html"}.issubset(names)

        with client.websocket_connect(f"/ws/sessions/{session_id}") as websocket:
            telemetry = websocket.receive_json()
            assert telemetry["run_id"] == session_id
            assert telemetry["state"] == "FINISHED"

        replay = client.post(f"/api/sessions/{session_id}/replay")
        assert replay.status_code == 200
        replay_id = replay.json()["session_id"]
        client.post(f"/api/sessions/{replay_id}/step")
        client.post(f"/api/sessions/{replay_id}/step")
        replay_result = client.get(f"/api/sessions/{replay_id}/result")
        assert replay_result.json()["manifest"]["replay_of_run_id"] == session_id
        assert replay_result.json()["manifest"]["replay_verified"] is True


def test_rule14_capability_api_and_combination_validation() -> None:
    with TestClient(app) as client:
        response = client.get("/api/capabilities", params={"validation_rule_id": "rule14"})
        script = client.get("/static/app.js")
        assert response.status_code == 200
        assert script.status_code == 200
        assert all(
            token in script.text
            for token in (
                "function syncExactCombinationAvailability()",
                "capabilityCatalog.verified_combinations",
                "function setExactSelectionAvailability(",
                "syncExactCombinationAvailability();",
            )
        )
        catalog = response.json()
        assert catalog["schema_version"] == "1.0"
        assert catalog["defaults"] == {
            "validation_rule_id": "rule14",
            "scenario_id": "head_on",
            "algorithm_id": "nominal",
            "tracker_id": "god",
        }
        capability_fields = {
            "readiness_grade",
            "dependency_available",
            "runtime_ready",
            "selectable",
            "supported_rules",
            "supported_scenarios",
            "supported_obstacles",
            "verified_combinations",
            "latest_evidence",
            "known_failure",
            "incompatibility_reason",
        }
        for category in ("rules", "scenarios", "algorithms", "trackers"):
            assert all(capability_fields.issubset(item) for item in catalog[category])
        assert next(item for item in catalog["scenarios"] if item["id"] == "head_on")["selectable"] is True
        algorithms = {item["id"]: item for item in catalog["algorithms"]}
        assert {name for name, item in algorithms.items() if item["selectable"]} == {"nominal", "vo", "sbmpc"}
        assert algorithms["psbmpc"]["incompatibility_reason"]
        assert algorithms["rrt"]["incompatibility_reason"]
        assert algorithms["rlmpc"]["incompatibility_reason"]
        trackers = {item["id"]: item for item in catalog["trackers"]}
        assert {name for name, item in trackers.items() if item["selectable"]} == {"god", "kf"}

        rejected = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "rule14",
                "scenario_id": "paper_ccta2023_head_on",
                "algorithm_id": "nominal",
                "tracker_id": "god",
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["detail"]["status"] == "INVALID_INPUT"
        assert "not a selectable rule14" in rejected.json()["detail"]["reason"]


def test_rule14_web_telemetry_preserves_latest_real_solve() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "rule14",
                "scenario_id": "head_on",
                "algorithm_id": "sbmpc",
                "tracker_id": "god",
                "t_end": 6.0,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]
        telemetry = None
        for _ in range(12):
            response = client.post(f"/api/sessions/{session_id}/step")
            assert response.status_code == 200
            telemetry = response.json()

        assert telemetry is not None
        assert telemetry["state"] == "FINISHED"
        assert telemetry["selected_rule"] == "rule14"
        assert telemetry["requested_algorithm"] == telemetry["executed_algorithm"] == "sbmpc"
        assert telemetry["requested_tracker"] == telemetry["executed_tracker"] == "god"
        assert telemetry["planner"]["solver_executed"] is False
        assert telemetry["planner"]["solve_id"] == 1
        assert telemetry["latest_planner_solve"]["solver_executed"] is True
        assert telemetry["latest_planner_solve"]["solve_id"] == 1
        assert len(telemetry["plans"]["prediction_horizon"]) == 60
        assert telemetry["encounters"][0]["validation_rule_id"] == "rule14"


def test_rule14_web_and_offline_trajectory_hashes_match(tmp_path: Path) -> None:
    request = {
        "validation_rule_id": "rule14",
        "scenario_id": "head_on",
        "algorithm_id": "nominal",
        "tracker_id": "god",
        "seed": 0,
        "t_end": 1.0,
    }
    with TestClient(app) as client:
        created = client.post("/api/sessions", json=request)
        assert created.status_code == 200, created.json()
        session_id = created.json()["session_id"]
        for _ in range(2):
            telemetry = client.post(f"/api/sessions/{session_id}/step")
            assert telemetry.status_code == 200
        assert telemetry.json()["state"] == "FINISHED"
        web_manifest = client.get(f"/api/sessions/{session_id}/result").json()["manifest"]

    offline = ExperimentRunner().run(
        RunSpec(**request, output_root=str(tmp_path / "offline"))
    )
    assert web_manifest["episode_hash"] == offline.manifest.episode_hash
    assert web_manifest["trajectory_hash"] == offline.manifest.trajectory_hash
