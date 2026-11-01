from typing import Any

import pytest

from highbay_sim.engine import RunRecord
from highbay_sim.events import SimulationEvent
from highbay_sim.metrics import DEFINITIONS, calculate_metrics


class Timeline:
    """Builds event sequences by hand, so metric tests do not depend on the engine."""

    def __init__(self) -> None:
        self.events: list[SimulationEvent] = []

    def add(self, time_s: float, kind: Any, order_id: str = "O1", **fields: Any) -> "Timeline":
        fields.setdefault("order_type", "storage")
        self.events.append(SimulationEvent(time_s, len(self.events), kind, order_id, **fields))
        return self

    def order(
        self,
        order_id: str,
        arrival_s: float,
        start_s: float,
        completion_s: float,
        order_type: str = "storage",
    ) -> "Timeline":
        """Add a complete order, keeping the timeline sorted only as far as tests need."""
        self.add(arrival_s, "order_arrived", order_id, order_type=order_type)
        self.add(start_s, "order_started", order_id, order_type=order_type, crane=1)
        self.add(completion_s, "order_completed", order_id, order_type=order_type, crane=1)
        return self

    def record(
        self,
        duration_s: float = 100.0,
        cell_count: int = 10,
        crane_count: int = 1,
        initial_occupied: int = 0,
    ) -> RunRecord:
        events = sorted(self.events, key=lambda event: (event.time_s, event.sequence))
        return RunRecord(
            events=tuple(events),
            orders=(),
            duration_s=duration_s,
            cell_count=cell_count,
            crane_count=crane_count,
            initial_occupied=initial_occupied,
        )


def test_throughput_counts_completions_in_window_per_hour() -> None:
    timeline = (
        Timeline()
        .order("O1", 0.0, 0.0, 5.0)
        .order("O2", 0.0, 0.0, 20.0)
        .order("O3", 0.0, 0.0, 30.0, order_type="retrieval")
    )
    metrics = calculate_metrics(timeline.record(duration_s=3610.0), warmup_s=10.0)
    assert metrics.throughput_total == pytest.approx(2.0)
    assert metrics.throughput_storage == pytest.approx(1.0)
    assert metrics.throughput_retrieval == pytest.approx(1.0)


def test_completions_exactly_at_window_limits_are_inside() -> None:
    timeline = Timeline().order("O1", 0.0, 0.0, 10.0).order("O2", 0.0, 0.0, 3610.0)
    metrics = calculate_metrics(timeline.record(duration_s=3610.0), warmup_s=10.0)
    assert metrics.throughput_total == pytest.approx(2.0)


def test_cycle_time_statistics_for_odd_count() -> None:
    timeline = (
        Timeline()
        .order("O1", 0.0, 0.0, 10.0)
        .order("O2", 0.0, 0.0, 20.0)
        .order("O3", 0.0, 0.0, 60.0)
    )
    cycle = calculate_metrics(timeline.record(), warmup_s=0.0).order_cycle_time
    assert cycle.mean == pytest.approx(30.0)
    assert cycle.median == pytest.approx(20.0)
    assert cycle.p95 == pytest.approx(60.0)
    assert cycle.max == pytest.approx(60.0)


def test_median_for_even_count_averages_middle_values() -> None:
    timeline = Timeline().order("O1", 0.0, 0.0, 10.0).order("O2", 0.0, 0.0, 20.0)
    cycle = calculate_metrics(timeline.record(), warmup_s=0.0).order_cycle_time
    assert cycle.median == pytest.approx(15.0)


@pytest.mark.parametrize(("count", "expected"), [(19, 19.0), (20, 19.0), (21, 20.0), (100, 95.0)])
def test_p95_uses_nearest_rank(count: int, expected: float) -> None:
    timeline = Timeline()
    for value in range(1, count + 1):
        timeline.order(f"O{value}", 0.0, 0.0, float(value))
    cycle = calculate_metrics(timeline.record(duration_s=200.0), warmup_s=0.0).order_cycle_time
    assert cycle.p95 == pytest.approx(expected)


def test_cycle_time_only_counts_orders_completed_in_window() -> None:
    timeline = Timeline().order("O1", 0.0, 0.0, 5.0).order("O2", 8.0, 8.0, 18.0)
    cycle = calculate_metrics(timeline.record(), warmup_s=10.0).order_cycle_time
    assert cycle.mean == pytest.approx(10.0)
    assert cycle.max == pytest.approx(10.0)


def test_waiting_time_uses_orders_started_in_window() -> None:
    timeline = Timeline().order("O1", 0.0, 5.0, 50.0).order("O2", 0.0, 20.0, 60.0)
    waiting = calculate_metrics(timeline.record(), warmup_s=10.0).order_waiting_time
    assert waiting.mean == pytest.approx(20.0)
    assert waiting.max == pytest.approx(20.0)


def test_no_data_gives_none_statistics_and_zero_throughput() -> None:
    metrics = calculate_metrics(Timeline().record(), warmup_s=0.0)
    assert metrics.throughput_total == 0.0
    assert metrics.order_cycle_time.mean is None
    assert metrics.order_cycle_time.median is None
    assert metrics.order_cycle_time.p95 is None
    assert metrics.order_cycle_time.max is None
    assert metrics.order_waiting_time.mean is None


def activity_timeline() -> Timeline:
    timeline = Timeline()
    timeline.add(0.0, "activity_started", crane=1, activity="moving_empty", end_s=20.0)
    timeline.add(20.0, "activity_started", crane=1, activity="handling", end_s=30.0)
    timeline.add(30.0, "activity_started", crane=1, activity="moving_loaded", end_s=40.0)
    timeline.add(95.0, "activity_started", crane=1, activity="handling", end_s=120.0)
    return timeline


def test_utilization_clips_activities_to_the_window() -> None:
    utilization = calculate_metrics(activity_timeline().record(), warmup_s=10.0).crane_utilization
    share = utilization[1]
    assert share.moving_empty == pytest.approx(10.0 / 90.0)
    assert share.handling == pytest.approx(15.0 / 90.0)
    assert share.moving_loaded == pytest.approx(10.0 / 90.0)
    assert share.idle == pytest.approx(55.0 / 90.0)


def test_utilization_shares_sum_to_one() -> None:
    share = calculate_metrics(activity_timeline().record(), warmup_s=10.0).crane_utilization[1]
    total = share.moving_empty + share.moving_loaded + share.handling + share.idle
    assert total == pytest.approx(1.0)


def test_every_crane_is_reported_even_when_idle() -> None:
    utilization = calculate_metrics(
        Timeline().record(crane_count=2), warmup_s=0.0
    ).crane_utilization
    assert set(utilization) == {1, 2}
    assert utilization[2].idle == pytest.approx(1.0)


def test_backlog_at_end_and_maximum() -> None:
    timeline = (
        Timeline()
        .add(1.0, "order_arrived", "O1")
        .add(2.0, "order_arrived", "O2")
        .add(3.0, "order_arrived", "O3")
        .add(4.0, "order_started", "O1", crane=1)
        .add(5.0, "order_started", "O2", crane=1)
    )
    metrics = calculate_metrics(timeline.record(), warmup_s=0.0)
    assert metrics.backlog_at_window_end == 1
    assert metrics.backlog_max_in_window == 3


def test_order_started_on_arrival_never_counts_as_backlog() -> None:
    timeline = Timeline().add(1.0, "order_arrived").add(1.0, "order_started", crane=1)
    assert calculate_metrics(timeline.record(), warmup_s=0.0).backlog_max_in_window == 0


def test_unfulfillable_order_leaves_the_backlog_at_once() -> None:
    timeline = Timeline().add(1.0, "order_arrived").add(1.0, "order_unfulfillable")
    metrics = calculate_metrics(timeline.record(), warmup_s=0.0)
    assert metrics.backlog_max_in_window == 0
    assert metrics.backlog_at_window_end == 0


def test_backlog_maximum_ignores_time_before_the_window() -> None:
    timeline = (
        Timeline()
        .add(1.0, "order_arrived", "O1")
        .add(2.0, "order_arrived", "O2")
        .add(3.0, "order_started", "O1", crane=1)
        .add(4.0, "order_started", "O2", crane=1)
    )
    assert calculate_metrics(timeline.record(), warmup_s=10.0).backlog_max_in_window == 0


def test_backlog_maximum_includes_value_carried_into_the_window() -> None:
    timeline = Timeline().add(1.0, "order_arrived", "O1").add(50.0, "order_started", "O1", crane=1)
    assert calculate_metrics(timeline.record(), warmup_s=10.0).backlog_max_in_window == 1


def test_occupancy_counts_load_units_physically_present() -> None:
    timeline = (
        Timeline()
        .add(5.0, "load_picked", "O1", order_type="storage")
        .add(8.0, "load_set", "O1", order_type="storage", location=(1, 1, 1, 1))
        .add(20.0, "load_picked", "O2", order_type="retrieval", location=(1, 1, 2, 1))
        .add(21.0, "load_picked", "O3", order_type="retrieval", location=(1, 1, 3, 1))
        .add(30.0, "load_set", "O2", order_type="retrieval")
    )
    metrics = calculate_metrics(timeline.record(initial_occupied=4), warmup_s=10.0)
    assert metrics.occupancy_at_window_start == pytest.approx(0.5)
    assert metrics.occupancy_at_window_end == pytest.approx(0.3)


def test_outcomes_count_the_whole_run() -> None:
    timeline = (
        Timeline()
        .order("O1", 0.0, 0.0, 5.0)
        .add(1.0, "order_arrived", "O2")
        .add(1.0, "order_unfulfillable", "O2")
        .add(2.0, "order_arrived", "O3")
    )
    metrics = calculate_metrics(timeline.record(), warmup_s=10.0)
    assert metrics.orders_generated == 3
    assert metrics.orders_completed == 1
    assert metrics.orders_unfulfillable == 1
    assert metrics.orders_unfinished == 1


def test_every_metric_has_a_definition_and_unit() -> None:
    assert set(DEFINITIONS) == {
        "throughput_per_hour",
        "order_cycle_time_s",
        "order_waiting_time_s",
        "crane_utilization",
        "backlog_orders",
        "storage_occupancy",
        "order_outcomes",
    }
    for entry in DEFINITIONS.values():
        assert entry["unit"]
        assert entry["definition"]


def test_warmup_outside_the_run_is_an_error() -> None:
    with pytest.raises(ValueError):
        calculate_metrics(Timeline().record(duration_s=10.0), warmup_s=10.0)
