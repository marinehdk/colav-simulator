from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from colav_simulator.experiment import ExperimentRunner, RunSpec
from gui_server.main import _select_primary_encounter, app


def _assert_primary_encounter_aliases(payload: dict) -> None:
    primary = payload["primary_encounter"]
    assert primary["target_label"] == f"TS{primary['target_id']}"
    assert payload["dcpa"] == primary["dcpa_m"]
    assert payload["tcpa"] == primary["tcpa_s"]
    assert payload["colregs"] == primary["encounter"]


def test_colregs_log_identifies_target_and_cleared_context() -> None:
    with TestClient(app) as client:
        script = client.get("/static/app.js")

    assert script.status_code == 200
    assert "const encounter = data.primary_encounter || null;" in script.text
    assert "function encounterTargetLabel(encounter)" in script.text
    assert "`TS${targetId}`" in script.text
    assert "COLREGs → ${ruleLabel}${targetSuffix}" in script.text
    assert "COLREGs → ${ENCOUNTER_LABELS.clear}（结束 ${previousRule}${previousTarget}）" in script.text
    assert "DCPA ${lvl.toUpperCase()}${targetSuffix}" in script.text


def test_map_wheel_zoom_is_anchored_at_pointer() -> None:
    with TestClient(app) as client:
        script = client.get("/static/app.js")

    assert script.status_code == 200
    assert "function zoomAtCanvasPoint(x, y, factor)" in script.text
    assert "const scaleRatio = nextScale / previousScale;" in script.text
    assert "panX = x - wrapper.clientWidth / 2 - (x - centerX) * scaleRatio;" in script.text
    assert "panY = y - wrapper.clientHeight / 2 - (y - centerY) * scaleRatio;" in script.text
    assert "zoomAtCanvasPoint(e.clientX - bounds.left, e.clientY - bounds.top, factor);" in script.text


def test_active_session_runtime_modules_are_served_as_single_lifecycle_owner() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        deployment = client.get("/static/app.js")
        config = client.get("/static/modules/config-shell.js")
        runtime = client.get("/static/modules/active-session-runtime.js")
        instance = client.get("/static/modules/session-runtime-instance.js")

    assert all(response.status_code == 200 for response in (page, deployment, config, runtime, instance))
    assert '<script type="module" src="/static/app.js' in page.text
    assert "activeSessionRuntime" in deployment.text and "activeSessionRuntime" in config.text
    assert "/api/sessions/current" in runtime.text
    assert "new WebSocket" in instance.text
    assert all("activeSessionId" not in source.text for source in (deployment, config))
    assert all("validation-session-" not in source.text for source in (deployment, config))


def test_header_uses_requested_session_labels() -> None:  # noqa: PLR0915
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/app.js")
        runtime = client.get("/static/modules/active-session-runtime.js")
        instance = client.get("/static/modules/session-runtime-instance.js")
        assert page.status_code == 200
        assert script.status_code == 200
        assert runtime.status_code == 200
        assert instance.status_code == 200
        assert "/api/sessions/current" in runtime.text
        assert "new WebSocket" in instance.text
        assert "Session restored:" in script.text
        assert "<h1>综合避碰仿真器</h1>" in page.text
        assert "Autonomous Ship COLAV" not in page.text
        assert (
            '<span id="conn-status">会话: 初始化</span>' in page.text
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
                "优先目标",
                ">DCPA<",
                ">TCPA<",
                "COLREGs规则",
                "与该目标船距离",
                "本船遥测状态",
                ">纬度<",
                ">经度<",
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
        assert 'data-algorithm="mid_mpc_ipopt"' in page.text
        assert 'data-algorithm="sbmpc"' not in page.text
        assert 'data-algorithm="vo"' in page.text
        assert 'data-algorithm="potocnik_colreg_fan_mpc"' in page.text
        assert 'data-algorithm="potocnik_simplified_mpc"' not in page.text
        assert 'class="algorithm-catalog"' in page.text
        assert '<option value="mid_mpc_ipopt" selected>Mid-MPC</option>' in page.text
        assert 'class="selection-card selected" type="button" data-algorithm="mid_mpc_ipopt"' in page.text
        assert '<span class="selection-name">Fan-MPC</span>' in page.text
        assert 'data-tracker="vimmjipda"' in page.text
        assert '<option value="god" selected>God Tracker</option>' in page.text
        assert "标准对遇 · G3 · 600s" in page.text
        assert "概率安全域 MPC 避碰" in page.text
        assert "ENC 高层路径规划" in page.text
        assert "雷达多目标跟踪" in page.text
        assert 'id="cardPlanner"' in page.text
        assert 'id="val-solver-executed"' in page.text
        assert 'class="planner-identity"' not in page.text
        assert 'id="val-planner-identity"' not in page.text
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
        assert 'id="val-surface-explanation"' in page.text
        assert 'id="val-surface-meta"' in page.text
        assert 'id="plannerSurface" width="280" height="280"' in page.text
        assert 'id="plannerSurfaceAttach"' in page.text
        assert 'id="plannerSurfaceDetach"' not in page.text
        assert 'id="plannerSurfacePanel"' in page.text
        assert 'id="voSurfaceLegend"' in page.text
        assert "? '速度决策空间'" in script.text
        assert "surfaceExplanation.hidden = !isVO" in script.text
        assert "surfaceMeta.hidden = isVO" in script.text
        assert "setPlannerSurfaceAttached(!plannerSurfaceAttached)" in script.text
        assert "drawPlannerSurfaceOnMap(data.os, diagnosticPlannerForData(data))" in script.text
        assert "if (surfaceType === 'fan') drawSimplifiedMpcFanOnMap(os, planner)" in script.text
        assert "plannerSurfaceType(currentDiagnosticPlanner())" in script.text
        assert "offsetY + scaledHeight - (point.y - minY) * scale" in script.text
        assert "panel.hidden = attached" in script.text
        assert "updateAttachedPlannerSurfacePosition" not in script.text
        assert all(
            f"label: '{label}'" in script.text
            for label in ("选中速度", "参考速度", "当前速度")
        )
        assert "简化 MPC · 扇形轨迹筛选" in script.text
        assert "envelope?.error === 'session_not_found'" in runtime.text
        assert "handleSessionNotFound(sessionId, generation);" in runtime.text
        assert "sessionCreationPromise && pendingSessionKey === requestKey" not in script.text
        assert "activeSessionKey === requestKey" not in script.text
        assert "apiRequest('/api/sessions'," not in script.text
        assert "`/api/sessions/${encodeURIComponent(sessionId)}/reset`" in runtime.text
        assert "validation-session-sync" not in script.text
        assert "nextSocket !== socket || generation !== socketGeneration" in runtime.text
        assert "!visibility.isVisible() || !visibility.hasFocus()" in runtime.text
        assert "candidate_heading_increments_rad" in script.text
        assert "`${horizonIntervals} × ${diagnosticPlanner.horizon_dt_s.toFixed(1)}s`" in script.text
        assert "目标在 ±90° 内，按首段航向差选择路径" in script.text
        assert "setText('val-best-speed-scale', '恒速')" in script.text
        assert "id === 'cardPerf' || !expanded" in script.text
        assert "sbmpcResponseRange(" not in script.text
        assert "responseRange?.threatActivation" in script.text
        assert "vo_velocity_space.v1" not in script.text
        assert "candidate_state_bits" in script.text
        assert "syncExactCombinationAvailability(id);" in script.text
        assert "if (kind === 'scenario_id') return true;" in script.text
        assert "planner/decision-space?solve_id=" in script.text
        assert "function drawVODecisionSpace(" in script.text
        assert "function voCandidateColor(" in script.text
        assert "角度相对本船艏向" not in script.text
        assert "objectiveHistoryWrap.hidden = !['sbmpc', 'mid_mpc_ipopt'].includes(algorithmId)" in script.text
        assert "Mid-MPC · IPOPT 优化轨迹" in script.text
        assert "Planner L0" in script.text
        assert "IPOPT 轨迹见海图" in script.text
        assert "Fan-MPC · 规则与安全筛选" in script.text


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
        assert 'id="cardBusyWater"' in page.text
        assert 'id="busyTargetCount" type="number" min="0" max="40" step="1"' in page.text
        assert 'id="targetColregs"' in page.text
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
        assert all(label in page.text for label in ("雷达探测圈（2 km）", "规划/响应范围"))
        assert all(label in page.text for label in ("纬度", "经度", "对地速度", "对地航向", "当前航向", "角速度"))
        assert "toFixed(4)" in script.text
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
        _assert_primary_encounter_aliases(first.json())

        second = client.post(f"/api/sessions/{session_id}/step")
        assert second.status_code == 200
        assert second.json()["state"] == "FINISHED"

        result = client.get(f"/api/sessions/{session_id}/result")
        assert result.status_code == 200
        assert result.json()["manifest"]["reproduction_status"] == "behavior_compatible_reconstruction"
        assert result.json()["manifest"]["evaluator_profile_id"] == "ccta_2023_demo-v1"
        assert result.json()["manifest"]["evaluation_schema_version"] == "2.0"

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


def test_primary_encounter_prefers_imminent_approaching_colreg_target() -> None:
    encounters = [
        {
            "target_id": 1,
            "encounter": "overtaking",
            "stage": 1,
            "distance_m": 1700.0,
            "dcpa_m": 25.0,
            "tcpa_s": 350.0,
            "signed_tcpa_s": 350.0,
        },
        {
            "target_id": 3,
            "encounter": "head_on",
            "stage": 2,
            "distance_m": 800.0,
            "dcpa_m": 30.0,
            "tcpa_s": 85.0,
            "signed_tcpa_s": 85.0,
        },
        {
            "target_id": 2,
            "encounter": "clear",
            "stage": 4,
            "distance_m": 100.0,
            "dcpa_m": 500.0,
            "tcpa_s": 10.0,
            "signed_tcpa_s": 10.0,
        },
    ]

    selected = _select_primary_encounter(encounters)

    assert selected is not None
    assert selected["target_id"] == 3
    assert selected["target_label"] == "TS3"
    assert selected["selection_reason"] == "composite_cpa_risk"
    assert selected["priority_score"] == pytest.approx(0.2279473684)
    assert selected["priority_weights"] == {"dcpa": 0.5, "tcpa": 0.3, "range": 0.2}


def test_primary_encounter_combines_dcpa_tcpa_and_range_before_rule_label() -> None:
    selected = _select_primary_encounter(
        [
            {
                "target_id": 2,
                "encounter": "clear",
                "stage": 4,
                "distance_m": 260.7,
                "dcpa_m": 170.5,
                "signed_tcpa_s": 30.4,
            },
            {
                "target_id": 4,
                "encounter": "crossing_give_way",
                "stage": 2,
                "distance_m": 2059.9,
                "dcpa_m": 1039.1,
                "signed_tcpa_s": 1015.7,
            },
        ]
    )

    assert selected is not None
    assert selected["target_id"] == 2
    assert selected["selection_reason"] == "composite_cpa_risk"
    assert selected["priority_components"] == pytest.approx(
        {"dcpa": 170.5 / 190.0, "tcpa": 30.4 / 300.0, "range": 260.7 / 2500.0}
    )


def test_primary_encounter_falls_back_to_nearest_contact() -> None:
    selected = _select_primary_encounter(
        [
            {"target_id": 4, "encounter": "clear", "stage": 4, "distance_m": 900.0},
            {"target_id": 2, "encounter": "clear", "stage": 1, "distance_m": 120.0},
        ]
    )

    assert selected is not None
    assert selected["target_id"] == 2
    assert selected["selection_reason"] == "nearest_available_contact"


def test_current_session_endpoint_returns_active_session() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={"scenario_id": "paper_ccta2023_multiship", "t_end": 0.2},
        )
        assert created.status_code == 200

        current = client.get("/api/sessions/current")
        assert current.status_code == 200
        assert current.json()["session_id"] == created.json()["session_id"]


def test_rule14_capability_api_and_combination_validation() -> None:
    with TestClient(app) as client:
        response = client.get("/api/capabilities", params={"validation_rule_id": "rule14"})
        script = client.get("/static/app.js")
        assert response.status_code == 200
        assert script.status_code == 200
        assert all(
            token in script.text
            for token in (
                "function syncExactCombinationAvailability(changedSelectId = null)",
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
        assert {name for name, item in algorithms.items() if item["selectable"]} == {
            "mid_mpc_ipopt",
            "nominal",
            "vo",
            "sbmpc",
            "potocnik_colreg_fan_mpc",
            "potocnik_simplified_mpc",
        }
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


def test_vo_decision_space_is_on_demand_and_not_in_telemetry() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "rule14",
                "scenario_id": "head_on",
                "algorithm_id": "vo",
                "tracker_id": "god",
                "t_end": 1.0,
            },
        )
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        empty = client.get(
            f"/api/sessions/{session_id}/planner/decision-space",
            params={"solve_id": 1},
        )
        assert empty.status_code == 204

        telemetry = client.post(f"/api/sessions/{session_id}/step")
        assert telemetry.status_code == 200
        document = telemetry.json()
        planner = document["latest_planner_solve"]
        solve_id = planner["solve_id"]
        assert solve_id == 1
        assert "candidate_state_bits" not in planner["algorithm_details"]
        assert "total_costs" not in planner["algorithm_details"]

        decision_space = client.get(
            f"/api/sessions/{session_id}/planner/decision-space",
            params={"solve_id": solve_id},
        )
        assert decision_space.status_code == 200
        snapshot = decision_space.json()
        assert snapshot["schema"] == "vo_velocity_space.v1"
        assert snapshot["solve_id"] == solve_id
        assert snapshot["shape"] == [32, 128]
        assert len(snapshot["candidate_state_bits"]) == 32 * 128
        assert all(value is None or isinstance(value, (int, float)) for value in snapshot["total_costs"])

        held = client.post(f"/api/sessions/{session_id}/step")
        assert held.status_code == 200
        held_planner = held.json()["planner"]
        assert held_planner["solver_executed"] is False
        assert held_planner["solve_id"] == solve_id

        held_decision_space = client.get(
            f"/api/sessions/{session_id}/planner/decision-space",
            params={"solve_id": solve_id},
        )
        assert held_decision_space.status_code == 200
        assert held_decision_space.json()["solve_id"] == solve_id

        stale = client.get(
            f"/api/sessions/{session_id}/planner/decision-space",
            params={"solve_id": solve_id + 1},
        )
        assert stale.status_code == 409
        missing = client.get(
            "/api/sessions/not-a-session/planner/decision-space",
            params={"solve_id": 1},
        )
        assert missing.status_code == 404

@pytest.mark.parametrize(
    "algorithm_id",
    ("potocnik_simplified_mpc", "potocnik_colreg_fan_mpc"),
)
def test_potocnik_web_session_uses_published_profile(algorithm_id: str) -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions",
            json={
                "validation_rule_id": "rule14",
                "scenario_id": "head_on",
                "algorithm_id": algorithm_id,
                "tracker_id": "god",
                "t_end": 1.0,
            },
        )
        assert created.status_code == 200, created.json()
        session_id = created.json()["session_id"]
        telemetry = None
        for _ in range(4):
            response = client.post(f"/api/sessions/{session_id}/step")
            assert response.status_code == 200, response.json()
            telemetry = response.json()
            if telemetry["state"] == "FINISHED":
                break

        assert telemetry is not None
        assert telemetry["requested_algorithm"] == algorithm_id
        assert telemetry["executed_algorithm"] == algorithm_id
        assert telemetry["latest_planner_solve"]["algorithm_id"] == algorithm_id
        assert telemetry["latest_planner_solve"]["status"] == "SUCCESS"
        assert telemetry["latest_planner_solve"]["algorithm_details"]["prediction_steps"] == 20
        assert telemetry["latest_planner_solve"]["algorithm_details"]["prediction_step_s"] == 5.0
        assert telemetry["latest_planner_solve"]["algorithm_details"]["solve_period_s"] == 5.0
        assert telemetry["latest_planner_solve"]["constraints"]["planning_zone"]["distance_m"] == 5556.0
        assert len(telemetry["plans"]["prediction_horizon"]) == 21


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
