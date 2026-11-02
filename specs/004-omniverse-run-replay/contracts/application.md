# Contract: Omniverse Application

## Setup

```text
omniverse/setup.ps1 [-KitTemplateDir PATH]
```

Clones `kit-app-template` at the fixed commit and builds it, by default in `C:\dev\omniverse\kit-app-template`. It does nothing that is already done. If the license terms have not been accepted, it stops with a message naming the terms and the command that shows the acceptance prompt.

| Exit code | Meaning |
|---|---|
| 0 | Ready |
| 1 | A step failed, and the message names it |
| 2 | The license terms have not been accepted |

## Starting

```text
omniverse/run-replay.ps1 RUN_FOLDER [-KitTemplateDir PATH]
```

`RUN_FOLDER` is a folder with `replay.json`, as written by `highbay-sim run --replay`. The script passes it as the setting `/exts/highbay.replay/run_folder`. The application can also start with no run, and a run can be chosen in its window. The script ends when the application closes.

## Controls

These match [the browser viewer](../../002-3d-run-replay/contracts/viewer.md).

| Control | Behavior |
|---|---|
| Open | Chooses a run folder. The new run is checked first. If it is valid, it replaces any open run, paused at time 0. |
| Play and pause | Starts or stops simulated time |
| Restart | Goes to time 0 and pauses |
| Time slider | Moves to the chosen time, covering the whole run |
| Speed | 1×, 10×, 60×, 600×, or 3,600× |
| Default view | Shows the whole warehouse, looking steeply along the aisles |
| Go to highest backlog | Moves to `reported.first_backlog_peak_s` and pauses |
| Viewport navigation | Kit's standard camera controls |
| Click in the viewport | The same selection rules as the browser viewer |

## Displayed information

The same figures, selection details, and legend as the browser viewer: simulated time, warm-up or measurement window, total backlog, backlog per aisle, orders waiting for a cell, occupancy with 6 decimal places, orders completed, and the run's identification.

## Looks

`appearance.py` is the only module that decides how objects look. A USD file can replace the simple look for one object type through a setting, on the command line or in the `.kit` file:

```text
--/exts/highbay.replay/looks/<type>=PATH
```

Types are `crane_mast`, `crane_carriage`, `load_unit`, `rack_upright`, `rack_beam`, and `transfer_point`. A file's origin and units must match the simple shape it replaces. If a file cannot be loaded, the simple look is used, and a warning names the type.

## Errors

The window shows a message, and no partial scene is created, when the following apply. A run that is already open stays open and unchanged.

- The folder has no `replay.json`, or the file cannot be read as JSON
- `format_version` is not supported, naming the found and supported versions
- A required part is missing or has the wrong structure

## Files

The application writes nothing to the run folder or to the repository. Kit keeps its own logs and caches outside them.

## Data collection

`highbay.replay.kit` sets `telemetry.enableAnonymousData = false`.

## Test mode

Automated tests start the application with a test script. The script writes its results to a named file and ends the process, as described in [research.md](../research.md). This is not a user feature.
