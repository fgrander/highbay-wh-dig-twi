# Contract: State Interface

**Interface version**: 1

This is the only way that run data reaches the scene and the display (FR-012). It is defined in `core/state_source.py`, and it imports nothing from Kit. It has no operation that writes anything, as Principle IV requires for later live sources.

## Operations

| Operation | Returns | Meaning |
|---|---|---|
| `describe()` | Warehouse description | Everything needed to build the scene. Called once, and the result does not change. |
| `time_range()` | `(start_s, end_s)` | The times available now. A recording's range is fixed. A live source's end can grow, so the display asks on every update. |
| `range_is_final` | Boolean | Whether the end of the range can no longer grow |
| `can_move_backward` | Boolean | Whether times before the current one can be requested |
| `state_at(time_s)` | Run state | The state at a time within the range, as in [data-model.md](../data-model.md) |
| `take_changes()` | Changed cells | Cells whose content changed since the last call, or a flag that all cells must be redrawn |
| `stored_load_units()` | Load units | All load units in cells, in location order, for redrawing all cells |
| `cell(location)` | Cell details | Current state and load unit of one cell |
| `load(key)` | Load unit details | A carried or stored load unit, or nothing if it no longer exists |
| `order(index)` | Order details | Number, type, times, cell, and aisle end of an order that a crane or load unit names |

## Behavior

- `state_at` raises an error for a time outside the range if the source cannot clamp it. The recorded source clamps, like the browser viewer.
- If `can_move_backward` is false, the display disables the time slider, restart, and the jump to the highest backlog.
- At the end of the range, playback stops if `range_is_final` is true. Otherwise it holds, and it continues when the end grows.
- `describe()` gives `reported` only when it is known. Without it, the display hides the jump to the highest backlog.
- Sources report problems by raising `StateSourceError` with a message naming the source and the problem. The display shows the message and keeps no partial scene.

## Connecting a source

The extension's `open_source(source)` takes any object that follows this interface, and it is the only way that a source reaches the scene and the window. Only `open_run_folder(path)` knows about recordings: it creates a `RecordedSource` and calls `open_source`.

## Sources in this feature

| Source | Purpose |
|---|---|
| `RecordedSource` | Reads a checked recording, using the same rules as `replay-state.js` |
| Scripted test source, in `tests/` | Written only from this document, with a growing range and no way to move backward, to prove SC-007 |

## Changes

The interface version changes when a change would stop an existing source from working. A later live source is expected to follow this version without a change.
