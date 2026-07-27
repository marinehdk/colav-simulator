from colav_simulator.integrations import IntegrationRegistry


def test_vimmjipda_config_is_project_resolved_when_available() -> None:
    registry = IntegrationRegistry()
    status = registry.statuses()["vimmjipda"]
    if not status.available:
        assert status.reason
        return
    tracker = registry.build_tracker("vimmjipda")
    assert tracker is not None
    assert hasattr(tracker, "track")
    assert hasattr(tracker, "reset")
