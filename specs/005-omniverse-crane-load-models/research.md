# Research: Omniverse Crane and Load Models

The project owner decided on the crane's form, on pairs that always move together, and on a pair counting as one article. The other decisions are proposals made during planning. Measurements were taken on 2026-11-03 on the project owner's computer, as in [feature 004](../004-omniverse-run-replay/research.md).

## Facts checked in a recording

Checked on one recording of the small sample warehouse, with 2,914 pick and set events. The stepped mode still has to be checked, by a task.

- Every `load_picked` and `load_set` event falls exactly on the end of its crane's latest `handling` activity. A recording therefore already tells what each handling step does, and where.
- At all 1,458 handling steps at a cell, the crane stands exactly at x = (bay − 0.5) × cell length and y = (level − 1) × cell height. Its recorded lift position is the floor of the cell.
- Handling takes 12 seconds in the sample, so a movement over this time is easy to see at 1×.

## Handling steps reach the display through the state interface

- **Decision**: `CraneState` gets an optional field, `handling`, with the kind of step, its cell, its start, and its end. `RecordedSource` fills it from the events above. The field defaults to None, so other sources keep working, and their forks stay at rest.
- **Rationale**: This meets the edge case for sources with no handling details, and needs no change to the recording.
- **Alternatives considered**: Working it out in the scene from the order would put recording rules outside the source.

## Fork positions are a pure function of time

- **Decision**: A new core module computes the forks and pair from a handling step, a time, and the layout. Extending takes the first 40% of the step, holding the next 20%, and returning the last 40%, each at a constant rate.
- **Rationale**: FR-008 asks for the same result however a time is reached, and such a function can be tested without Kit.
- **Alternatives considered**: A smooth profile looks slightly better, but nothing in the recording supports any profile, and this is display only.

## No visible lift

- **Decision**: The pair stays at one height, the same on the forks and in the cell. The carriage stays at its recorded height, as FR-003 requires.
- **Rationale**: A lift would need the carriage or forks to leave their recorded heights, for a movement of a few centimeters based on placeholder dimensions.
- **Alternatives considered**: Moving the forks alone by a small lift can be added when real dimensions exist.

## Fewest writes to the array of stored pairs

- **Decision**: During a pick at a cell, the stored instance is hidden from the start of the step, and the carried pair is shown at the cell's position, which looks identical. It stays there until the forks start to return, and then moves with them. During a set, the carried pair moves out with the forks and stays at the cell's position until the recorded event stores it. The scene writes the arrays only when their content changed.
- **Rationale**: A write to the array costs far more than moving a prim (see below). This way each step causes about as many writes as before: the hide at the start of a pick replaces the write at its event, which then changes nothing. Figures keep following the recording.
- **Alternatives considered**: Moving a stored instance by rewriting the positions array in every frame would be measurably slower at 100,000 cells.

## One instance per cell, with one prototype per pair

- **Decision**: The instancer keeps one instance per cell. Each prototype is a pair, a group with two load units. There is one prototype per distinct pair of types, and one per article color for undefined articles.
- **Rationale**: Instance numbers, hiding, picking, and the arrays' size stay as in feature 004, and the number of objects does not double.
- **Alternatives considered**: Two instances per cell would change instance numbering, double the arrays, and allow nothing this feature needs.

## Load unit geometry

- **Decision**: Each stack is one mesh. A board stack has one box per board, with every second board set slightly inward so that each is visible. A sheet stack is one block with bands, in two materials bound through subsets of its faces. It shows about 20 bands rather than 1000 sheets, and needs no texture file.
- **Rationale**: One mesh per stack is cheap to instance. Bands stay readable from a distance, where 1000 real lines would blur. A shiny material on both bands gives the laminated look.
- **Alternatives considered**: A texture needs a file and has to be scaled per size. One prim per board multiplies the prims per prototype by 30, for no visible difference.

A sample image shows both stacks as readable, with individual boards and bands, at 8 prototypes and with 30 boards in each board stack.

## Models are generated while opening a run

- **Decision**: Generation moves from `omniverse/models/build_crane_model.py` into the extension's core, as standard library code that returns USDA text. `appearance.py` loads this text into an anonymous layer and copies it into the stage's root layer with `Sdf.CopySpec`.
- **Rationale**: A run opened from the window can have any size of warehouse, so a crane cannot be generated before starting. Nothing is written to disk. Measured: the copy keeps material bindings and connections, adjusted to the new path, and leaves no reference to the anonymous layer in the stage, so a built scene stays free of machine details. A reference to an anonymous layer would not.
- **Alternatives considered**: Generated files in a temporary folder would need a new folder for each warehouse, and would put its path into the scene.

## Detailed models are the default

- **Decision**: The setting `/exts/highbay.replay/models` is `detailed` by default, and `simple` gives feature 004's scene, which has one box per load and no fork movement. A file given for a look still replaces the generated model. Tests of feature 004 run with `simple`.
- **Rationale**: User Story 1 expects the new crane on opening a run. FR-017 asks for the simple shapes to keep working, which also protects the existing tests of them.

## Selection follows the shown crane

- **Decision**: With detailed models, `pick_crane` uses a list of boxes for columns, travel gear, top beam, carriage ends, forks at their current extension, and the pair. They are computed from the same dimensions as the model, in one core module. A click through the opening between the columns does not select the crane. With simple models, the existing boxes stay in use, and the comparison with the browser viewer is unchanged.
- **Rationale**: FR-005, and a test in Kit compares the boxes with the model's actual bounds, so that the two cannot drift apart.

## Forks must clear the rack beams

- **Decision**: Forks sit between the top of a rack beam and the bottom of the pair, so their height is derived from the layout: from half a rack member above the carriage's height, plus a small gap, up to the pair's bottom. In the sample, this gives about 6 cm. The rack member's thickness moves from `appearance.py` to `layout.py` for this.
- **Rationale**: The recorded height is the floor of the cell, where a rack beam lies. A test checks that no fork or load box overlaps a beam at the lowest level (User Story 1, scenario 5).

## Pair definitions in TOML

- **Decision**: One TOML file holds load unit types and pair definitions, read with `tomllib`, by default from the extension's `data` folder and otherwise from a setting. It is read each time a run is opened.
- **Rationale**: FR-011 asks for versionable data. `tomllib` is in the standard library of both Python versions, so the core stays free of dependencies, and unlike JSON the file can have comments.
- **Alternatives considered**: YAML, as in the warehouse files, is not in Kit's standard library.

## Aisle light

- **Decision**: One rectangular light per aisle, along the top of the aisle and shining down, with a fixed share of the existing light. Its intensity is set in implementation against sample images of a full aisle.
- **Rationale**: Its cost is low (see below), and the number of lights follows the number of aisles.
- **Open risk**: So far the effect has only been seen in an aisle with mostly empty racks, where an intensity of 5,000 visibly lightens the shadows. A rack full of stock blocks more light, so the value is not yet known, and SC-004 decides it. If this light is not enough, a light moving with each crane is the next option.

## Status colors

- **Open risk**: The status strips on the columns are narrow, and did not stand out in the view along the aisle. SC-004 asks for the activity to be recognizable there, so implementation may have to make them wider, or to color larger parts.

## Measured performance

A prototype with 100,000 cells, 30% of them hidden, 8 pair prototypes each with a board stack of 30 boards and a sheet stack of 20 bands, at 1920×1080 in RTX Real-Time mode without a window, with the whole warehouse in view, and with the frame limiter and eco mode off:

| Case | Frames per second | Slowest frame |
|---|---|---|
| No changes | 282 | 8 ms |
| No changes, with 20 aisle lights | 285 | 6 ms |
| `invisibleIds` written in every frame | 39 | 32 ms |

**Limits of this prototype**: It had no racks and no cranes, and calculated no state, and was run only once. Feature 004's full scene reached 32 frames per second at this size. The numbers show that pair prototypes and lights are not the main cost, but they do not prove SC-006. The performance tests do that, with the full scene.

## Sizes of the sample stacks

- **Decision**: In the default definitions, both types are 1.4 m long and 1.25 m wide, which fits in half of a sample cell (1.6 m by 1.5 m). A particle board stack is 30 boards of 19 mm, and a sheet stack 1000 sheets of 0.3 mm, for heights of 0.57 m and 0.30 m.
- **Rationale**: Real boards of up to 2.8 m do not fit in half of these cells. These sizes are placeholders, as stated in the spec, and are changed only in the data file.
