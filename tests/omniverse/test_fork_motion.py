"""Fork and pair positions in a handling step, with values worked out by hand.

Cells are 1.0 m wide and aisles too, so each rack's center is (1 + 1) / 2 = 1 m from the aisle's.
Rack 1 lies towards -z. A step lasts 10 s from t = 100 s, so extending ends at 104 s, and returning
starts at 106 s.
"""

import pytest

from highbay.replay.core.fork_motion import REST, fork_pose
from highbay.replay.core.layout import create_layout
from highbay.replay.core.state_source import HandlingStep

LAYOUT = create_layout(
    {
        "aisle_count": 2,
        "racks_per_aisle": 2,
        "bays_per_rack": 5,
        "levels_per_rack": 3,
        "cell": {"height_m": 2.0, "length_m": 4.0, "width_m": 1.0},
    }
)
RACK_1 = (2, 1, 3, 2)
RACK_2 = (2, 2, 3, 2)


def step(kind: str, location: tuple[int, int, int, int] | None) -> HandlingStep:
    return HandlingStep(kind, location, 100.0, 110.0)


@pytest.mark.parametrize(
    ("time_s", "share_of_reach"),
    [
        (100.0, 0.0),
        (102.0, 0.5),
        (104.0, 1.0),
        (105.0, 1.0),
        (106.0, 1.0),
        (108.0, 0.5),
        (110.0, 0.0),
    ],
)
@pytest.mark.parametrize(("location", "sign"), [(RACK_1, -1.0), (RACK_2, 1.0)])
@pytest.mark.parametrize("kind", ["pick", "set"])
def test_forks_extend_towards_the_cells_rack_and_return(
    kind: str,
    location: tuple[int, int, int, int],
    sign: float,
    time_s: float,
    share_of_reach: float,
) -> None:
    pose = fork_pose(step(kind, location), time_s, LAYOUT)
    assert pose.extension_m == pytest.approx(sign * share_of_reach)


@pytest.mark.parametrize(
    ("time_s", "offset"),
    [(100.0, -1.0), (102.0, -1.0), (105.0, -1.0), (106.0, -1.0), (108.0, -0.5), (109.9, -0.025)],
)
def test_picked_pair_waits_in_the_cell_and_returns_with_the_forks(
    time_s: float, offset: float
) -> None:
    pose = fork_pose(step("pick", RACK_1), time_s, LAYOUT)
    assert pose.pair_offset_m == pytest.approx(offset)
    assert pose.pair_on_crane
    assert pose.hidden_cell == RACK_1


@pytest.mark.parametrize(
    ("time_s", "offset"),
    [(100.0, 0.0), (102.0, 0.5), (104.0, 1.0), (106.0, 1.0), (108.0, 1.0), (109.9, 1.0)],
)
def test_set_pair_goes_out_with_the_forks_and_stays_at_the_cell(
    time_s: float, offset: float
) -> None:
    pose = fork_pose(step("set", RACK_2), time_s, LAYOUT)
    assert pose.pair_offset_m == pytest.approx(offset)
    assert pose.pair_on_crane
    assert pose.hidden_cell is None  # The recording still has it on the crane.


@pytest.mark.parametrize("kind", ["pick", "set"])
def test_forks_rest_at_an_aisle_end(kind: str) -> None:
    assert fork_pose(step(kind, None), 105.0, LAYOUT) == REST


def test_forks_rest_with_no_step() -> None:
    assert fork_pose(None, 105.0, LAYOUT) == REST
    assert REST.extension_m == 0.0
    assert REST.pair_offset_m == 0.0
    assert not REST.pair_on_crane
    assert REST.hidden_cell is None


def test_a_step_of_no_length_shows_the_forks_at_rest() -> None:
    pose = fork_pose(HandlingStep("pick", RACK_1, 100.0, 100.0), 100.0, LAYOUT)
    assert pose.extension_m == 0.0


def test_times_outside_a_step_stay_at_its_limits() -> None:
    assert fork_pose(step("set", RACK_1), 90.0, LAYOUT).extension_m == 0.0
    assert fork_pose(step("set", RACK_1), 120.0, LAYOUT).extension_m == 0.0


def test_one_rack_per_aisle_extends_towards_that_rack() -> None:
    layout = create_layout(
        {
            "aisle_count": 1,
            "racks_per_aisle": 1,
            "bays_per_rack": 5,
            "levels_per_rack": 3,
            "cell": {"height_m": 2.0, "length_m": 4.0, "width_m": 1.0},
        }
    )
    assert fork_pose(step("pick", (1, 1, 3, 2)), 105.0, layout).extension_m == pytest.approx(-1.0)
