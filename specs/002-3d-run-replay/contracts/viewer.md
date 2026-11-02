# Contract: Viewer

The viewer runs in a browser with WebGL 2 and loads everything from the local server. It makes no other network requests, and it never writes to the server.

## Modules

Logic modules do not use the document or three.js, so they can be tested directly.

| Module | Type | Responsibility |
|---|---|---|
| `replay-file.js` | Logic | Load and check replay data, with clear errors |
| `replay-state.js` | Logic | `stateAt(time)`: the state in `data-model.md` |
| `motion.js` | Logic | Axis and crane position at a time |
| `layout.js` | Logic | 3D positions and sizes from the warehouse definition |
| `playback.js` | Logic | Simulated clock, speed, restart, moving to a time, staying within the run |
| `picking.js` | Logic | Cell from a selection ray and the layout |
| `appearance.js` | Display | One function for each object type, creating its 3D object from dimensions |
| `scene.js` | Display | Build the scene, and update it from a state |
| `panels.js` | Display | Controls, figures, details, and error message |
| `main.js` | Display | Connect the parts |

`appearance.js` is the only module that decides how objects look (FR-007). Replacing simple shapes with detailed models means changing only this module and adding model files.

## Controls

| Control | Behavior |
|---|---|
| Play and pause | Starts or stops simulated time |
| Restart | Goes to time 0 and pauses |
| Time slider | Moves to the chosen time, covering the whole run |
| Speed | 1×, 10×, 60×, 600×, or 3,600× |
| Default view | Returns the camera to show the whole warehouse |
| Go to highest backlog | Moves to `reported.first_backlog_peak_s` and pauses |
| Drag, right-drag, and scroll in the view | Rotate, move, and zoom |
| Click in the view | A crane selects the crane, and its details offer any carried load unit for selection. Otherwise the first load unit along the ray is selected, through empty cells, with its cell's details also shown. With no load unit along the ray, the nearest cell is selected. Anywhere else clears the selection. |

## Displayed information

- **Figures, always visible**: simulated time, warm-up or measurement window, total backlog, backlog per aisle, orders waiting for a cell, occupancy, orders completed, and the run's identification. Occupancy is shown with 6 decimal places, the same format as `report.md`.
- **Selection details**: as in the spec's User Story 2. Load units from initial stock show "initial stock" in place of an order.
- **Legend**: a color for each article, and the crane colors for each activity.

Default colors for crane activity: moving empty is blue, moving loaded is orange, handling is purple, and idle is gray. Article colors come from a fixed sequence in `articles` order, so a run always looks the same.

## Error messages

A message replaces the 3D view when:

- The replay file cannot be loaded or read as JSON
- `format_version` is not supported, naming the found and supported versions
- A required part is missing or has the wrong structure
- WebGL 2 is not available in the browser

## Test hook

`window.highbayViewer` exposes read-only values for automated tests and benchmarks: the current time, playing state, speed, current state, selection, and last error. It also exposes `ready`, a promise resolved when the viewer has loaded a replay or shown an error.

## Benchmark mode

Opening the viewer with `?benchmark=1` plays at 600× for 20 seconds while the camera orbits the warehouse, then displays and exposes the average frames per second and the slowest frame.
