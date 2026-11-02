# Research: 3D Run Replay

The project owner decided that the viewer runs in a web browser and uses simple shapes that can be replaced later, and that the simulation stays in Python. The other decisions are proposals made during planning.

## 3D library

- **Decision**: three.js 0.170.0, using instanced drawing for cells and load units. A copy of the needed files and the license is kept in `src/highbay_sim/viewer/vendor/`.
- **Rationale**: It is the most widely used WebGL library, and instanced drawing is suited to many identical boxes. Keeping a copy satisfies the no-internet requirement. Availability of this exact version was confirmed during planning.
- **Alternatives considered**: Babylon.js is capable but larger. Direct WebGL would need far more code.

## No build step

- **Decision**: Plain ES modules served as they are.
- **Rationale**: Node.js is not installed, a build step would add a second toolchain, and the code is small enough without one.
- **Alternatives considered**: TypeScript and a bundler give type checks, but they require Node.js.

## Replay file

- **Decision**: One uncompressed `replay.json` with compact rows, written only when `--replay` is given. It contains no timestamps or machine details, and times are not rounded.
- **Rationale**: At the planning target of about 165,000 events and at most 100,000 stock rows, the estimated size is about 25 MB, well below the 100 MB limit, so compression is not needed. Rounding would merge events less than a time step apart, so the viewer could show a state that never occurred, such as a backlog that does not reach the reported maximum (FR-020, SC-006). Python writes each time as the shortest decimal that reads back as the same value, and browsers read it as the same value, so the file stays byte-identical for identical inputs. The file is easy to inspect and compare.
- **Alternatives considered**: Compression and binary formats save space that is not needed, and make reproducibility and debugging harder.

## Building replay data from events

- **Decision**: Build `replay.json` after a run from `RunRecord`, the warehouse definition, and the calculated metrics. Add `start_position` and `target_position` to `activity_started` events for movements.
- **Rationale**: This fulfills FR-002 directly, because writing happens after simulation has finished. The engine already calculates these positions, and exposing them means the viewer never needs to work out which transfer point was used. They are also useful to later consumers. Result files do not contain events, so they do not change, and a test enforces this.
- **Alternatives considered**: Deriving positions from orders would duplicate engine rules in the replay writer. Streaming with `on_event` adds nothing, because replay is written after the run.

## Reported figures

- **Decision**: The Python replay writer stores the run's reported metrics and the time of the backlog peak in the replay file. The viewer shows state derived from events, and tests compare its end-of-run figures with the stored values.
- **Rationale**: FR-008 prohibits the viewer from calculating results. The peak time uses the same grouping of equal-time events as the backlog metric, so the time always matches the reported maximum (FR-020).

## State at a simulated time

- **Decision**: One pure function applies events in order up to a time. Moving forward continues from the current state, and moving backward starts again from the initial state. Crane activity and position are found by searching each crane's own list of activities.
- **Rationale**: Applying about 165,000 simple events takes an estimated few milliseconds in a browser, well within SC-003, so stored snapshots are not needed. One code path also makes FR-012 true by construction. A performance test measures it.
- **Alternatives considered**: Periodic snapshots make seeks faster but add a second path for reaching a state.

## Crane motion

- **Decision**: Each axis follows its own symmetric trapezoidal profile from the start of the movement, using the same formula as the simulation. Each axis stops when it reaches its target, so the faster axis waits at its target until the movement ends.
- **Rationale**: It matches FR-011 and the simulation's calculation, where a movement takes as long as the slower axis. A test compares the JavaScript with hand-calculated positions.

## Rendering at the planning target

- **Decision**: Draw load units as one instanced mesh, updating only instances that changed. Draw each rack as its frame only, not one object per cell. Cranes are individual simple objects.
- **Rationale**: Up to 100,000 stored load units fit in a single instanced draw call, and racks need no more than lines for a readable view. Frame rate depends on the graphics hardware, so it is checked with a benchmark mode and a manual step.
- **Risk**: 100,000 boxes on integrated graphics may approach the 30 frames per second limit. If so, the fallback is to draw only the visible faces of each rack block.

## Selecting objects

- **Decision**: Calculate the selected cell from the selection ray and rack geometry, rather than testing every instance. Cranes use standard ray tests against their few objects.
- **Rationale**: Empty cells must also be selectable (FR-015), and have no drawn object. Calculating from geometry costs the same at any warehouse size. A hit on an occupied cell selects its load unit, whose details include the cell's, and a hit on a crane carrying a load unit selects the crane, whose details include the load unit, which can then be selected from those details.

## Aisle spacing

- **Decision**: For display only, an aisle's width equals the cell width, and neighbouring aisle blocks are separated by 10% of the cell width. Racks extend out from the aisle: rack 1 on one side, rack 2 on the other.
- **Rationale**: The simulation does not define spacing, as the spec assumes. Any fixed rule meets it, and these values look plausible without new input fields.

## Local server

- **Decision**: `http.server.ThreadingHTTPServer`, bound to `127.0.0.1` on a free port, serving only GET and HEAD for the viewer's files and the chosen replay file. Content types are set explicitly by file extension.
- **Rationale**: It needs no new dependency and is reachable only from the same computer. Explicit types matter on Windows, where the registry can give JavaScript a type that browsers refuse to run as a module.
- **Alternatives considered**: FastAPI and similar frameworks are not needed for serving a few files.

## Testing the viewer

- **Decision**: Playwright for Python drives headless Chromium. Logic modules are imported into the page and called directly, and behavior is tested through the actual user interface and a test hook that reports displayed state.
- **Rationale**: It fits the existing pytest setup and needs no Node.js. Availability for Python 3.14 was confirmed during planning (version 1.64.1). Chromium must be downloaded once for development, which `uv sync` does not do. Users of the viewer do not need it.
- **Limitation**: Headless Chromium uses software rendering, so it cannot measure SC-002. It can check that the scene draws, but frame rate needs real hardware.

## Frame rate check

- **Decision**: A benchmark mode, opened with `?benchmark=1`, plays the replay while orbiting the camera for a fixed time and reports frames per second.
- **Rationale**: It gives a repeatable number for SC-002 on the machine in use. Passing is a manual check.
