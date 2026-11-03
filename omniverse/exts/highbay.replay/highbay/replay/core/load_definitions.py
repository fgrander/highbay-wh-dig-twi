"""Which load each article shows, from a data file, with warnings for what cannot be used.

A cell's load is one whole unit, or two parts of a split stack that lie end to end along the aisle.
Nothing here stops a run from opening: what cannot be used falls back to a simple shape.
"""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .layout import Layout, Vector

CUT_M = 0.01
SAME_LENGTH_M = 0.001
KINDS = ("board_stack", "paper_pallet", "file")
_STACK_KINDS = ("board_stack", "paper_pallet")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True, slots=True)
class LoadUnitType:
    name: str
    kind: str
    length_m: float
    width_m: float
    height_m: float
    smallest_part_m: float | None = None
    count: int = 0
    thickness_m: float = 0.0
    base_thickness_m: float = 0.0
    color: str | None = None
    edge_color: str | None = None
    file: str | None = None


@dataclass(frozen=True, slots=True)
class ShownUnit:
    """One unit in a load. With no type, it is a simple box."""

    type_name: str
    unit_type: LoadUnitType | None
    length_m: float
    width_m: float
    height_m: float
    center_x: float

    @property
    def size(self) -> Vector:
        return (self.length_m, self.height_m, self.width_m)


@dataclass(frozen=True, slots=True)
class ShownLoad:
    units: tuple[ShownUnit, ...]

    @property
    def size(self) -> Vector:
        """Returns the size of the whole load, as (along the aisle, up, across)."""
        length = sum(unit.length_m for unit in self.units) + CUT_M * (len(self.units) - 1)
        return (
            length,
            max(unit.height_m for unit in self.units),
            max(unit.width_m for unit in self.units),
        )

    @property
    def label(self) -> str:
        if len(self.units) == 1:
            return self.units[0].type_name
        return " + ".join(f"{unit.type_name} {unit.length_m:g} m" for unit in self.units)


@dataclass(slots=True)
class LoadDefinitions:
    types: dict[str, LoadUnitType]
    loads: dict[str, Any]
    warnings: list[str]


class _BadField(Exception):
    pass


def _positive(content: dict[str, Any], field: str) -> float:
    value = content.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise _BadField(f"{field} must be a number above 0, not {value!r}")
    return float(value)


def _whole_positive(content: dict[str, Any], field: str) -> int:
    value = content.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _BadField(f"{field} must be a whole number above 0, not {value!r}")
    return value


def _color(content: dict[str, Any], field: str) -> str | None:
    value = content.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not _COLOR.match(value):
        raise _BadField(f'{field} must look like "#rrggbb", not {value!r}')
    return value


def _read_type(name: str, content: Any, folder: Path) -> LoadUnitType:
    if not isinstance(content, dict):
        raise _BadField("it must be a table")
    kind = content.get("kind")
    if kind not in KINDS:
        raise _BadField(f"kind must be one of {', '.join(KINDS)}, not {kind!r}")
    length = _positive(content, "length_m")
    width = _positive(content, "width_m")
    smallest = None
    if "smallest_part_m" in content:
        smallest = _positive(content, "smallest_part_m")
    if kind == "file":
        file = content.get("file")
        if not isinstance(file, str) or not file:
            raise _BadField(f"file must name a file, not {file!r}")
        return LoadUnitType(
            name,
            kind,
            length,
            width,
            _positive(content, "height_m"),
            smallest,
            file=str(folder / file),
        )
    count = _whole_positive(content, "count")
    thickness = _positive(content, "thickness_m")
    base = _positive(content, "base_thickness_m") if kind == "paper_pallet" else 0.0
    return LoadUnitType(
        name,
        kind,
        length,
        width,
        count * thickness + base,
        smallest,
        count,
        thickness,
        base,
        _color(content, "color"),
        _color(content, "edge_color"),
    )


def read_load_definitions(path: Path | str) -> LoadDefinitions:
    """Reads a definitions file. Anything that cannot be used gives a warning that names it."""
    path = Path(path)
    try:
        content = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        return LoadDefinitions({}, {}, [f"The load definitions in {path} cannot be read: {error}"])
    except ValueError as error:  # Includes text that is not valid TOML or UTF-8.
        return LoadDefinitions({}, {}, [f"The load definitions in {path} are damaged: {error}"])
    types = {}
    warnings = []
    declared = content.get("types", {})
    for name, value in (declared if isinstance(declared, dict) else {}).items():
        try:
            types[name] = _read_type(name, value, path.parent)
        except _BadField as error:
            warnings.append(f'The load unit type "{name}" cannot be used: {error}.')
    loads = content.get("loads", {})
    return LoadDefinitions(types, loads if isinstance(loads, dict) else {}, warnings)


def _entries(value: Any) -> list[dict[str, Any]] | None:
    """Returns the units of a definition, or None if it has the wrong form."""
    if not isinstance(value, list) or not 1 <= len(value) <= 2:
        return None
    if not all(isinstance(entry, dict) and isinstance(entry.get("type"), str) for entry in value):
        return None
    return value


def _entry_length(entry: dict[str, Any]) -> float | None:
    value = entry.get("length_m")
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return None
    return float(value)


def _split_problem(
    article: str, entries: list[dict[str, Any]], types: dict[str, Any]
) -> str | None:
    known = [types[entry["type"]] for entry in entries if entry["type"] in types]
    if len(known) < 2:
        return None
    first, second = known
    if first.smallest_part_m is None or first.name != second.name:
        return f'The load of article "{article}" is split, but {first.name} cannot be split.'
    lengths = [_entry_length(entry) for entry in entries]
    if None in lengths:
        return f'The load of article "{article}" is split, and needs the length of both parts.'
    total = lengths[0] + lengths[1]  # type: ignore[operator]
    if abs(total - first.length_m) > SAME_LENGTH_M:
        return (
            f'The parts of article "{article}", {lengths[0]:g} m and {lengths[1]:g} m, '
            f"do not add up to {first.length_m:g} m."
        )
    if min(lengths) < first.smallest_part_m:  # type: ignore[type-var]
        return (
            f'A part of article "{article}", of {lengths[0]:g} m and {lengths[1]:g} m, is below '
            f"the smallest part of {first.smallest_part_m:g} m."
        )
    return None


def _shown_units(
    article: str,
    entries: list[dict[str, Any]],
    types: dict[str, LoadUnitType],
    layout: Layout,
    warnings: list[str],
) -> ShownLoad:
    simple_length, simple_height, simple_width = layout.load_size()
    sized = []
    for entry in entries:
        unit_type = types.get(entry["type"])
        if unit_type is None:
            warnings.append(
                f'The load of article "{article}" names the unknown type "{entry["type"]}", '
                "which is shown as a simple shape."
            )
        full = unit_type.length_m if unit_type else simple_length
        # A part with no length is shown as half, and has a warning from the check of the split.
        fallback = full if len(entries) == 1 else full / 2
        sized.append((entry["type"], unit_type, _entry_length(entry) or fallback))
    total = sum(length for _name, _type, length in sized) + CUT_M * (len(sized) - 1)
    start = -total / 2
    units = []
    for name, unit_type, length in sized:
        units.append(
            ShownUnit(
                name,
                unit_type,
                length,
                unit_type.width_m if unit_type else simple_width,
                unit_type.height_m if unit_type else simple_height,
                start + length / 2,
            )
        )
        start += length + CUT_M
    return ShownLoad(tuple(units))


def _fit_problem(article: str, load: ShownLoad, layout: Layout) -> str | None:
    length, height, width = load.size
    space = layout.cell_height - layout.load_base_height()
    if length <= layout.cell_length and width <= layout.cell_width and height <= space:
        return None
    return (
        f'The load of article "{article}", {length:g} m by {width:g} m and {height:g} m high, '
        f"does not fit a cell of {layout.cell_length:g} m by {layout.cell_width:g} m "
        f"with {space:g} m of height."
    )


def resolve_loads(
    definitions: LoadDefinitions, articles: list[str], layout: Layout
) -> tuple[list[ShownLoad | None], list[str]]:
    """Returns the load of each article, or None if it has none, and all warnings for this run."""
    warnings = list(definitions.warnings)
    loads: list[ShownLoad | None] = []
    for article in articles:
        entries = _entries(definitions.loads.get(article))
        if entries is None:
            warnings.append(f'No load is defined for article "{article}", so it looks simple.')
            loads.append(None)
            continue
        if len(entries) == 2:
            problem = _split_problem(article, entries, definitions.types)
            if problem:
                warnings.append(problem)
        load = _shown_units(article, entries, definitions.types, layout, warnings)
        problem = _fit_problem(article, load, layout)
        if problem:
            warnings.append(problem)
        loads.append(load)
    return loads, list(dict.fromkeys(warnings))
