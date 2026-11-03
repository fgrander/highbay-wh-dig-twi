# Highbay Replay extension

Replays a recorded warehouse run in Omniverse Kit. See [the application contract](../../../specs/004-omniverse-run-replay/contracts/application.md) and [its changes](../../../specs/005-omniverse-crane-load-models/contracts/application.md) for its controls and settings, and [the state interface](../../../specs/004-omniverse-run-replay/contracts/state-interface.md) with [its changes](../../../specs/005-omniverse-crane-load-models/contracts/state-interface.md) for connecting another source.

## Cranes

By default, each crane is generated from the warehouse's dimensions when a run is opened: two columns with the load between them, joined at the top, with a carriage and two fork sections. To see the simple shapes instead, start with `--/exts/highbay.replay/models=simple`.

The columns and the carriage's end frames show the crane's activity color. During a handling step at a cell, both sections extend towards the cell's rack, and the load moves with them. This is display only: figures and details follow the recording, so a cell can look empty during a pick while it still counts as occupied, until the step's end.

## Loads

`data/load_definitions.toml` decides what each article's load looks like, and it is read each time a run is opened. To use a copy, start with `-LoadDefinitions PATH`. A load is one of these:

- One whole unit, on both fork sections, such as a paper pallet, or a stack of particle boards.
- Two parts of a split stack, one on each section, with a cut that can be anywhere.

To the simulation, a load is always one article and one order, whole or split, so throughput figures count loads. This is why result files still say that multi-load handling is not modeled. It holds as long as both parts of a split stack are always stored and retrieved together.

An article with no definition shows as a simple box in its color. Anything that cannot be used gives a warning in the window, and the run still opens. The rules are in [the data model](../../../specs/005-omniverse-crane-load-models/data-model.md).

## Dimensions to change

The following are real values from the project owner, in `data/load_definitions.toml`: the length and width of paper (5.61 m by 2.08 m) and of particle boards (at most 5.6 m by 2.07 m), the smallest part of a split stack (1.5 m), and the base board below the paper (30 mm).

All other values are placeholders until real ones are known:

| Values | Where to change them |
|---|---|
| Numbers and thicknesses of boards and sheets, and colors of loads | `data/load_definitions.toml` |
| Cell sizes, levels, and bays. These change travel times, and so results | The warehouse file, such as `samples/replay/real-size-warehouse.yaml` |
| The crane's parts, such as its columns, travel gear, and forks | The constants in `highbay/replay/core/crane_dimensions.py` |
| Where each section stands | `SECTION_FROM_END_M` in `highbay/replay/core/crane_dimensions.py` |
| Aisle light | `AISLE_LIGHT_INTENSITY` in `highbay/replay/appearance.py` |

## Replacing a look

To use your own model for a type, give a USD file for it when starting the application:

```text
omniverse/run-replay.ps1 out/small --/exts/highbay.replay/looks/crane_mast=C:\models\mast.usd
```

| Type | Object | Origin of the file |
|---|---|---|
| `crane_mast` | The crane's columns | At half the warehouse's height, at the crane's center |
| `crane_carriage` | The carriage with its forks | On a cell's floor, at the crane's center |
| `load_unit` | A load unit, stored or carried, with `simple` models only | The load unit's center |
| `rack_upright` | An upright of a rack | The upright's center |
| `rack_beam` | A beam of a rack | The beam's center |
| `transfer_point` | The marker at an aisle end | The marker's center |

The file needs a default prim, in meters, with Y up, and at the real size, as the simple shape's scale is not applied to it. Positions and behavior do not change, but selection keeps using the generated crane's size, and a warning says so.

To move its forks, a carriage file needs the prims `Section1` and `Section2`, each with the children `Middle` and `Top`, with a `xformOp:translate`. To extend by a distance along z, `Top` moves by that distance and `Middle` by half of it. Without these, the forks stay at rest.

A load unit's own file is given in the definitions, as a type of the kind `file`, with its origin on the floor at the center of the unit.

Colors reach a model through the `primvars:displayColor` of its top prim, which its parts inherit if they have no material of their own.

If a file cannot be loaded, the simple shape is used, and a warning names it.
