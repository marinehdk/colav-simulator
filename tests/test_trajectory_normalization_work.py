"""Nested planner evidence must not expand normalization work exponentially."""

from collections.abc import ItemsView

from colav_simulator.experiment.persistence import _semantic_trajectory_value


def test_nested_trajectory_dictionary_is_traversed_once_per_level() -> None:
    visits = []

    class TracedDict(dict):
        def items(self) -> ItemsView[str, object]:
            visits.append(self)
            return super().items()

    document = TracedDict(value=1.0, run_id="exclude-run-identity")
    expected = {"value": 1.0}
    for _ in range(12):
        document = TracedDict(evidence=document)
        expected = {"evidence": expected}
    assert _semantic_trajectory_value(document) == expected
    assert len(visits) == 13
