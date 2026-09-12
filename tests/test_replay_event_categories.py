"""Replay event-journal category labeling (ticket #73, Seam A).

The timeline marker categories are a backend-owned, deterministic labeling
projection over the RECORDED journal: identity, sim time, order and details
must come back byte-identical across repeated reads, with ``category`` purely
additive.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from test_replay_window import RUN_WINDOW, api_client, make_window_run, runs_root  # noqa: F401

from gui_server.replay import EVENT_CATEGORIES, EventCategories, RunReplayStore


def test_category_mapping_is_deterministic_and_covers_recorded_kinds() -> None:
    cases = {
        "collision": EventCategories.SAFETY_FAILURE,
        "grounding": EventCategories.SAFETY_FAILURE,
        "planner_solved": EventCategories.PLANNER,
        "mid_mpc_solve": EventCategories.PLANNER,
        "primary_threat_selected": EventCategories.RISK_LIFECYCLE,
        "encounter_lifecycle": EventCategories.RISK_LIFECYCLE,
        "goal_reached": EventCategories.MISSION,
        "time_limit": EventCategories.MISSION,
        "algorithm_handoff": EventCategories.HANDOFF,
        "session_started": EventCategories.RUNTIME,
        "totally_unknown_kind": EventCategories.RUNTIME,
    }
    for event_type, expected in cases.items():
        assert EVENT_CATEGORIES.categorize(event_type) == expected, event_type
        # Deterministic across repeats.
        assert EVENT_CATEGORIES.categorize(event_type) == EVENT_CATEGORIES.categorize(event_type)


def test_events_endpoint_returns_category_additively_with_recorded_order(
    api_client: TestClient,  # noqa: F811
) -> None:
    first = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/events")
    assert first.status_code == 200
    document = first.json()
    assert document["count"] == 3
    assert [event["category"] for event in document["events"]] == [
        "RUNTIME",
        "RISK_LIFECYCLE",
        "SAFETY_FAILURE",
    ]
    # Recorded fields are untouched: identity, time, order, details.
    assert [event["type"] for event in document["events"]] == [
        "session_started",
        "threat_schedule_update",
        "collision",
    ]
    assert document["events"][1]["details"] == {"target_id": 1}
    # Repeated reads return the same order/identity (no mutation, no retiming).
    second = api_client.get(f"/api/runs/{RUN_WINDOW}/replay/events")
    assert second.json() == document


def test_categories_summary_matches_the_journal(
    runs_root: Path,  # noqa: F811
) -> None:
    make_window_run(runs_root, RUN_WINDOW)
    store = RunReplayStore(runs_root)
    document = store.replay_events(RUN_WINDOW, limit=100)
    assert document["categories"] == sorted({event["category"] for event in document["events"]})
