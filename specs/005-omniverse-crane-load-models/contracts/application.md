# Contract: Application Changes

This extends [the application contract of feature 004](../../004-omniverse-run-replay/contracts/application.md). Commands, controls, and errors not named here stay the same.

## Settings

| Setting | Values | Default |
|---|---|---|
| `/exts/highbay.replay/models` | `detailed` or `simple` | `detailed` |
| `/exts/highbay.replay/load_definitions` | Path to a definitions file | The extension's `data/load_definitions.toml` |

`simple` gives the scene of feature 004: one box per load unit, simple cranes, no fork movement, and no aisle lights.

## Starting

```text
omniverse/run-replay.ps1 RUN_FOLDER [-KitTemplateDir PATH] [-LoadDefinitions PATH]
```

`-LoadDefinitions` passes its absolute path as the setting above. Further arguments still go to Kit.

## Definitions file

TOML, read each time a run is opened, so a change shows when the run is opened again. Its rules are in [data-model.md](../data-model.md).

```toml
[types.particle_board]
kind = "board_stack"
length_m = 1.4
width_m = 1.25
count = 30
thickness_m = 0.019

[types.laminated_sheets]
kind = "sheet_stack"
length_m = 1.4
width_m = 1.25
count = 1000
thickness_m = 0.0003

[types.my_scanned_stack]
kind = "file"
file = "looks/my_stack.usd"
length_m = 1.4
width_m = 1.25
height_m = 0.6

[pairs]
"oak-panel-18mm" = ["particle_board", "laminated_sheets"]
"paper-a4-80g" = ["laminated_sheets", "laminated_sheets"]
```

## Looks

The settings of feature 004 stay. With detailed models:

| Type | Effect of a file |
|---|---|
| `crane_mast`, `crane_carriage` | Replaces the generated part. Selection keeps using the generated dimensions, and a warning says so. |
| `rack_upright`, `rack_beam`, `transfer_point` | As in feature 004 |
| `load_unit` | Has no effect, as pair definitions decide this, and a warning says so |

A carriage file that has `Platform`-relative stages `Section1/Top`, `Section1/Middle`, `Section2/Top`, and `Section2/Middle` gets its forks moved. Without them, they stay at rest.

## Displayed information

| Where | Added |
|---|---|
| Details of a stored pair | `Pair: <type 1> + <type 2>`, after the article |
| Details of a crane carrying a pair | `Pair: <type 1> + <type 2>`, after what it carries |
| Window | A section that lists the warnings of the open run. It is empty and hidden when there are none. |

With `simple` models, or for an undefined article, the `Pair` line is left out.

## Selection

- With detailed models, a click selects a crane if it hits a box as in [data-model.md](../data-model.md). A click through the opening between its columns goes on to what lies behind.
- The order stays as in feature 004: a crane, otherwise a load unit, otherwise a cell.
- With `simple` models, selection is as in feature 004.
- During a handling step, the recording decides what a click selects, as it does for the figures. During a pick, a click on the cell that looks empty still selects its load unit, until the recorded event. A click that hits the crane's boxes, including a pair on or beside its forks, selects the crane first.

## Not changed

The simulation, `highbay-sim`, the format of `replay.json`, result files, and the browser viewer. Only the recorded software version changes, to 0.5.0.
