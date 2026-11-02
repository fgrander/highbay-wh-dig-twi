"""3D layout, with values worked out by hand from the table in data-model.md.

Cells are 4 m long, 3 m high, and 1.5 m wide, in 5 bays and 2 levels:
aisle width 1.5, block gap 0.15.
"""

from typing import Any

import pytest

from conftest import Modules

TWO_RACKS = {
    "aisle_count": 2,
    "racks_per_aisle": 2,
    "bays_per_rack": 5,
    "levels_per_rack": 2,
    "cell": {"height_m": 3.0, "length_m": 4.0, "width_m": 1.5},
}
ONE_RACK = {**TWO_RACKS, "racks_per_aisle": 1}


def layout_value(modules: Modules, layout: dict[str, Any], script: str) -> Any:
    return modules.run(
        "const { createLayout } = await imports('layout.js');"
        f"const layout = createLayout(args[0]); return {script};",
        layout,
    )


def test_block_measures_with_two_racks(modules: Modules) -> None:
    # Block width: 2 x 1.5 + 1.5 = 4.5. Aisle 2 is at 4.5 + 0.15 = 4.65.
    assert layout_value(modules, TWO_RACKS, "layout.aisleWidth") == pytest.approx(1.5)
    assert layout_value(modules, TWO_RACKS, "layout.blockWidth") == pytest.approx(4.5)
    assert layout_value(modules, TWO_RACKS, "layout.blockGap") == pytest.approx(0.15)
    assert layout_value(modules, TWO_RACKS, "layout.aisleCenterZ(1)") == pytest.approx(0.0)
    assert layout_value(modules, TWO_RACKS, "layout.aisleCenterZ(2)") == pytest.approx(4.65)


def test_block_measures_with_one_rack(modules: Modules) -> None:
    # Block width: 1.5 + 1.5 = 3. Aisle 2 is at 3 + 0.15 = 3.15.
    assert layout_value(modules, ONE_RACK, "layout.blockWidth") == pytest.approx(3.0)
    assert layout_value(modules, ONE_RACK, "layout.aisleCenterZ(2)") == pytest.approx(3.15)


def test_cell_box(modules: Modules) -> None:
    box = layout_value(modules, TWO_RACKS, "layout.cellBox([2, 1, 3, 2])")
    # x: bay 3 center is 2.5 x 4 = 10. y: level 2 starts at 3, with its center at 4.5.
    # z: aisle 2 at 4.65, and rack 1 at -(1.5 + 1.5) / 2 from it.
    assert box["center"] == pytest.approx([10.0, 4.5, 3.15])
    assert box["size"] == pytest.approx([4.0, 3.0, 1.5])


def test_rack_two_is_on_the_other_side(modules: Modules) -> None:
    assert layout_value(modules, TWO_RACKS, "layout.cellBox([2, 2, 1, 1]).center") == pytest.approx(
        [2.0, 1.5, 6.15]
    )


def test_aisle_ends(modules: Modules) -> None:
    assert layout_value(modules, TWO_RACKS, "layout.endX('left')") == pytest.approx(0.0)
    assert layout_value(modules, TWO_RACKS, "layout.endX('right')") == pytest.approx(20.0)


def test_crane_position_in_the_world(modules: Modules) -> None:
    world = layout_value(modules, TWO_RACKS, "layout.craneWorldPosition(2, [6.0, 3.0])")
    assert world == pytest.approx([6.0, 3.0, 4.65])


def test_bounds_with_two_racks(modules: Modules) -> None:
    # z: aisle 1 at 0 minus half an aisle and a rack; aisle 2 at 4.65 plus the same.
    bounds = layout_value(modules, TWO_RACKS, "layout.bounds()")
    assert bounds["min"] == pytest.approx([0.0, 0.0, -2.25])
    assert bounds["max"] == pytest.approx([20.0, 6.0, 6.9])


def test_bounds_with_one_rack(modules: Modules) -> None:
    # Only rack 1 exists, so the far side of the last aisle ends at half an aisle: 3.15 + 0.75.
    bounds = layout_value(modules, ONE_RACK, "layout.bounds()")
    assert bounds["min"] == pytest.approx([0.0, 0.0, -2.25])
    assert bounds["max"] == pytest.approx([20.0, 6.0, 3.9])


def test_cell_count(modules: Modules) -> None:
    assert layout_value(modules, TWO_RACKS, "layout.cellCount") == 40
