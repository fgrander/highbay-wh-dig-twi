"""Input models, loading, validation, and content hashes.

Field rules are enforced by the pydantic models. Rules across fields are checked on the parsed
document, so they are still reported when another field of the same document is invalid.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from highbay_sim.events import OrderType

End = Literal["left", "right"]
Role = Literal["inbound", "outbound"]
ENDS: tuple[End, End] = ("left", "right")
ROLES: tuple[Role, Role] = ("inbound", "outbound")
DOCUMENT_PATH = "(document)"

PositiveInt = Annotated[int, Field(ge=1)]
PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
Text = Annotated[str, Field(min_length=1)]


class _InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class CellDimensions(_InputModel):
    height_m: PositiveFloat
    length_m: PositiveFloat
    width_m: PositiveFloat


class Layout(_InputModel):
    aisle_count: PositiveInt
    racks_per_aisle: Literal[1, 2] = 2
    bays_per_rack: PositiveInt
    levels_per_rack: PositiveInt
    cell: CellDimensions

    @property
    def cell_count(self) -> int:
        return self.aisle_count * self.racks_per_aisle * self.bays_per_rack * self.levels_per_rack


class AxisMotion(_InputModel):
    speed_m_s: PositiveFloat
    acceleration_m_s2: PositiveFloat


class CraneParameters(_InputModel):
    horizontal: AxisMotion
    vertical: AxisMotion
    pick_time_s: NonNegativeFloat
    set_time_s: NonNegativeFloat


class TransferEnds(_InputModel):
    left: list[Role] = []
    right: list[Role] = []


class TransferPoints(_InputModel):
    default: TransferEnds
    aisles: dict[int, TransferEnds] = {}


class StockLocation(_InputModel):
    aisle: PositiveInt
    rack: PositiveInt
    bay: PositiveInt
    level: PositiveInt


class StockEntry(_InputModel):
    location: StockLocation
    article: Text


class WarehouseDefinition(_InputModel):
    schema_version: Literal[1]
    name: Text
    layout: Layout
    crane: CraneParameters
    transfer_points: TransferPoints
    storage_rule: Literal["nearest_free", "random_free"]
    initial_stock: list[StockEntry] = []

    def ends_with_role(self, aisle: int, role: Role) -> list[End]:
        """Return the aisle's ends having a transfer point of this role, left before right."""
        ends = self.transfer_points.aisles.get(aisle, self.transfer_points.default)
        return [end for end in ENDS if role in getattr(ends, end)]


class GeneratedParameters(_InputModel):
    orders_per_hour: NonNegativeFloat
    storage_share: Annotated[float, Field(ge=0, le=1)]
    article_weights: dict[Text, NonNegativeFloat]

    @field_validator("article_weights")
    @classmethod
    def _weights_have_positive_total(cls, weights: dict[str, float]) -> dict[str, float]:
        if sum(weights.values()) <= 0:
            raise ValueError("article weights must have a positive total")
        return weights


class ExplicitOrder(_InputModel):
    time_s: NonNegativeFloat
    type: OrderType
    article: Text


class Scenario(_InputModel):
    schema_version: Literal[1]
    name: Text
    seed: Annotated[int, Field(ge=0)]
    duration_s: PositiveFloat
    warmup_s: NonNegativeFloat
    generated: GeneratedParameters | None = None
    orders: list[ExplicitOrder] | None = None


@dataclass(frozen=True)
class InputProblem:
    file: str
    field_path: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.field_path}: {self.message}"


class InputError(Exception):
    """One or more inputs are invalid; `problems` lists every problem found."""

    def __init__(self, problems: list[InputProblem]) -> None:
        super().__init__("\n".join(str(problem) for problem in problems))
        self.problems = problems


@dataclass(frozen=True)
class Loaded[T]:
    model: T
    sha256: str


def load_warehouse(path: Path) -> Loaded[WarehouseDefinition]:
    return _load(path, WarehouseDefinition, _warehouse_cross_field_problems)


def load_scenario(path: Path) -> Loaded[Scenario]:
    return _load(path, Scenario, _scenario_cross_field_problems)


def load_inputs(
    warehouse_path: Path, scenario_path: Path
) -> tuple[Loaded[WarehouseDefinition], Loaded[Scenario]]:
    """Load both files, reporting the problems of both together."""
    problems: list[InputProblem] = []
    warehouse: Loaded[WarehouseDefinition] | None = None
    scenario: Loaded[Scenario] | None = None
    try:
        warehouse = load_warehouse(warehouse_path)
    except InputError as error:
        problems += error.problems
    try:
        scenario = load_scenario(scenario_path)
    except InputError as error:
        problems += error.problems
    if warehouse is None or scenario is None:
        raise InputError(problems)
    return warehouse, scenario


def content_hash(document: Any) -> str:
    """Hash parsed content, so that line endings and key order do not change the result."""
    canonical = json.dumps(
        _with_text_keys(document), sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _with_text_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _with_text_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_with_text_keys(item) for item in value]
    return value


def _load[T: BaseModel](path: Path, model: type[T], cross_field_problems: Any) -> Loaded[T]:
    file = str(path)
    document = _read_document(path)
    found = [
        InputProblem(file, _field_path(error["loc"]), error["msg"])
        for error in _validation_errors(model, document)
    ]
    found += [
        InputProblem(file, field_path, message)
        for field_path, message in cross_field_problems(document)
    ]
    if found:
        raise InputError(found)
    return Loaded(model.model_validate(document), content_hash(document))


def _read_document(path: Path) -> dict[Any, Any]:
    file = str(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise InputError(
            [InputProblem(file, DOCUMENT_PATH, f"cannot read file: {error}")]
        ) from error
    except yaml.YAMLError as error:
        message = " ".join(str(error).split())
        raise InputError([InputProblem(file, DOCUMENT_PATH, f"invalid YAML: {message}")]) from error
    if not isinstance(document, dict):
        raise InputError([InputProblem(file, DOCUMENT_PATH, "the document must be a mapping")])
    return document


def _validation_errors(model: type[BaseModel], document: dict[Any, Any]) -> list[Any]:
    try:
        model.model_validate(document)
    except ValidationError as error:
        return list(error.errors())
    return []


def _field_path(location: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in location) or DOCUMENT_PATH


def _mapping(value: Any) -> dict[Any, Any]:
    return value if isinstance(value, dict) else {}


def _sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _positive_int(value: Any) -> int | None:
    return value if type(value) is int and value >= 1 else None


def _number(value: Any) -> float | None:
    return float(value) if type(value) in (int, float) else None


def _warehouse_cross_field_problems(document: dict[Any, Any]) -> list[tuple[str, str]]:
    return _transfer_point_problems(document) + _stock_problems(document)


def _transfer_point_problems(document: dict[Any, Any]) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    aisle_count = _positive_int(_mapping(document.get("layout")).get("aisle_count"))
    transfer_points = _mapping(document.get("transfer_points"))
    overrides = _mapping(transfer_points.get("aisles"))

    served_by_override = 0
    for aisle, ends in overrides.items():
        path = f"transfer_points.aisles.{aisle}"
        problems += _repeated_role_problems(path, ends)
        if aisle_count is not None and type(aisle) is int and not 1 <= aisle <= aisle_count:
            problems.append((path, f"aisle {aisle} does not exist"))
            continue
        served_by_override += 1
        problems += [
            (path, f"aisle {aisle} has no {role} transfer point") for role in _missing_roles(ends)
        ]

    if "default" in transfer_points:
        path = "transfer_points.default"
        problems += _repeated_role_problems(path, transfer_points["default"])
        if aisle_count is None or served_by_override < aisle_count:
            problems += [
                (path, f"the default configuration has no {role} transfer point")
                for role in _missing_roles(transfer_points["default"])
            ]
    return problems


def _repeated_role_problems(path: str, ends: Any) -> list[tuple[str, str]]:
    problems = []
    for end in ENDS:
        roles = _sequence(_mapping(ends).get(end))
        for role in ROLES:
            if roles.count(role) > 1:
                problems.append((f"{path}.{end}", f"{role} is listed more than once"))
    return problems


def _missing_roles(ends: Any) -> list[Role]:
    listed = [role for end in ENDS for role in _sequence(_mapping(ends).get(end))]
    return [role for role in ROLES if role not in listed]


def _stock_problems(document: dict[Any, Any]) -> list[tuple[str, str]]:
    layout = _mapping(document.get("layout"))
    limits = {
        "aisle": _positive_int(layout.get("aisle_count")),
        "rack": 2 if "racks_per_aisle" not in layout else _positive_int(layout["racks_per_aisle"]),
        "bay": _positive_int(layout.get("bays_per_rack")),
        "level": _positive_int(layout.get("levels_per_rack")),
    }
    problems: list[tuple[str, str]] = []
    seen: set[tuple[int, ...]] = set()
    for index, entry in enumerate(_sequence(document.get("initial_stock"))):
        location = _mapping(_mapping(entry).get("location"))
        values = [_positive_int(location.get(part)) for part in limits]
        if None in values:
            continue
        path = f"initial_stock.{index}.location"
        key = tuple(value for value in values if value is not None)
        if any(
            limit is not None and value > limit
            for value, limit in zip(key, limits.values(), strict=True)
        ):
            problems.append((path, f"location {key} does not exist"))
        if key in seen:
            problems.append((path, f"location {key} already holds stock"))
        seen.add(key)
    return problems


def _scenario_cross_field_problems(document: dict[Any, Any]) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    duration = _number(document.get("duration_s"))
    warmup = _number(document.get("warmup_s"))
    if duration is not None and warmup is not None and warmup >= duration:
        problems.append(("warmup_s", "the warm-up must be shorter than the duration"))

    if ("generated" in document) == ("orders" in document):
        problems.append(("orders", "a scenario needs exactly one of generated or orders"))

    if duration is not None:
        for index, order in enumerate(_sequence(document.get("orders"))):
            time_s = _number(_mapping(order).get("time_s"))
            if time_s is not None and time_s >= duration:
                problems.append((f"orders.{index}.time_s", "the order is after the run ends"))
    return problems
