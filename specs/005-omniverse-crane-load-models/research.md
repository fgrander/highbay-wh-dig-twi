# Research: Omniverse Crane and Load Models

The project owner decided on the crane's form, on a load that always moves together, and on a load counting as one article. The other decisions are proposals made during planning. Measurements were taken on 2026-11-03 on the project owner's computer, as in [feature 004](../004-omniverse-run-replay/research.md).

## Facts checked in a recording

Checked on recordings of the small sample warehouse in both modes, by `tests/omniverse/test_handling_in_recordings.py`.

- Every `load_picked` and `load_set` event falls exactly on the end of its crane's latest `handling` activity. A recording therefore already tells what each handling step does, and where.
- At all 1,458 handling steps at a cell, the crane stands exactly at x = (bay − 0.5) × cell length and y = (level − 1) × cell height. Its recorded lift position is the floor of the cell.
- Handling takes 12 seconds in the sample, so a movement over this time is easy to see at 1×.

## Handling steps reach the display through the state interface

- **Decision**: `CraneState` gets an optional field, `handling`, with the kind of step, its cell, its start, and its end. `RecordedSource` fills it from the events above. The field defaults to None, so other sources keep working, and their forks stay at rest.
- **Rationale**: This meets the edge case for sources with no handling details, and needs no change to the recording.
- **Alternatives considered**: Working it out in the scene from the order would put recording rules outside the source.

## Fork positions are a pure function of time

- **Decision**: A new core module computes the forks and load from a handling step, a time, and the layout. Extending takes the first 40% of the step, holding the next 20%, and returning the last 40%, each at a constant rate.
- **Rationale**: FR-008 asks for the same result however a time is reached, and such a function can be tested without Kit.
- **Alternatives considered**: A smooth profile looks slightly better, but nothing in the recording supports any profile, and this is display only.

## No visible lift

- **Decision**: The load stays at one height, the same on the forks and in the cell. The carriage stays at its recorded height, as FR-003 requires.
- **Rationale**: A lift would need the carriage or forks to leave their recorded heights, for a movement of a few centimeters based on placeholder dimensions.
- **Alternatives considered**: Moving the forks alone by a small lift can be added when real dimensions exist.

## Fewest writes to the array of stored loads

- **Decision**: During a pick at a cell, the stored instance is hidden from the start of the step, and the carried load is shown at the cell's position, which looks identical. It stays there until the forks start to return, and then moves with them. During a set, the carried load moves out with the forks and stays at the cell's position until the recorded event stores it. The scene writes the arrays only when their content changed.
- **Rationale**: A write to the array costs far more than moving a prim (see below). This way each step causes about as many writes as before: the hide at the start of a pick replaces the write at its event, which then changes nothing. Figures keep following the recording.
- **Alternatives considered**: Moving a stored instance by rewriting the positions array in every frame would be measurably slower at 100,000 cells.

## One instance per cell, with one prototype per load

- **Decision**: The instancer keeps one instance per cell. Each prototype is a load, a group with one unit or two parts. There is one prototype per distinct load definition, and one per article color for undefined articles.
- **Rationale**: Instance numbers, hiding, picking, and the arrays' size stay as in feature 004, and the number of objects does not double.
- **Alternatives considered**: Two instances per cell would change instance numbering, double the arrays, and allow nothing this feature needs.

## Load unit geometry

- **Decision**: Each stack is one mesh. A board stack has one box per board, with every second board set slightly inward so that each is visible. A paper pallet has a wooden pallet of a deck, runners, and a base, with one block of sheets on it. The block has bands, in two materials bound through subsets of its faces. It shows about 20 bands rather than 1000 sheets, and needs no texture file. The forks carry a pallet from below, not through its openings, as the placeholder forks stand under the two halves of a cell.
- **Rationale**: One mesh per stack is cheap to instance. Bands stay readable from a distance, where 1000 real lines would blur. A shiny material on both bands gives the laminated look. The project owner corrected the load's name from Malette to a pallet with paper on 2026-11-03, before any of this geometry was built. The measurement below had no pallets, so T042 has to confirm its cost.
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

- **Decision**: With detailed models, `pick_crane` uses a list of boxes for columns, travel gear, top beam, carriage ends, forks at their current extension, and the load. They are computed from the same dimensions as the model, in one core module. A click through the opening between the columns does not select the crane. With simple models, the existing boxes stay in use, and the comparison with the browser viewer is unchanged.
- **Rationale**: FR-005, and a test in Kit compares the boxes with the model's actual bounds, so that the two cannot drift apart.

## Columns stand outside the whole cell length

- **Decision**: The columns are positioned from the full cell length, not from the 0.85 share used for a single load in feature 004.
- **Rationale**: With the first position, a load in two halves of a sample cell reached ±1.50 m, while the carriage's end frames started at ±1.43 m, so the load would pass through them.

## Forks must clear the rack beams

- **Decision**: Forks sit between the top of a rack beam and the bottom of the load, so their height is derived from the layout: from half a rack member above the carriage's height, plus a small gap, up to the load's bottom. In the sample, this gives about 6 cm. The rack member's thickness moves from `appearance.py` to `layout.py` for this.
- **Rationale**: The recorded height is the floor of the cell, where a rack beam lies. A test checks that no fork or load box overlaps a beam at the lowest level (User Story 1, scenario 5).

## Load definitions in TOML

- **Decision**: One TOML file holds load unit types and load definitions, read with `tomllib`, by default from the extension's `data` folder and otherwise from a setting. It is read each time a run is opened.
- **Rationale**: FR-011 asks for versionable data. `tomllib` is in the standard library of both Python versions, so the core stays free of dependencies, and unlike JSON the file can have comments.
- **Alternatives considered**: YAML, as in the warehouse files, is not in Kit's standard library.

## Aisle light

- **Decision**: One rectangular light per aisle, along the top of the aisle and shining down, at an intensity of 5,000.
- **Rationale**: Its cost is low (see below), and the number of lights follows the number of aisles. Images along an aisle of the small sample's size, with 96% of its cells occupied, compared 0, 5,000, and 30,000. At 0, the crane and racks are dark, and at 30,000, stock and the crane's colors wash out. At 5,000, the crane and its color are clear.
- **Limits**: This was judged only at the sample's height of 15 m. As the light is at the top of the aisle, a much taller warehouse will be darker at its floor, and the value may need to follow the height. Stock in these images is still the simple shape, and pale stacks may change how this looks.

## Activity color on whole columns

- **Decision**: The columns and the carriage's end frames have no material, so they show the activity color as a whole. The narrow status strips of the first model are removed.
- **Rationale**: Looking along an aisle, only the outer side of one column can be seen, and the strips were on the sides facing the racks, where they could not be seen at all. With whole columns, each of the four activities can be told apart along a full aisle (SC-004, images in `images/`). Columns end below the top beam, as faces in the same place flickered when rendered.
- **Alternatives considered**: Moving strips to the outer side leaves little to color next to the ladder.

## Measured performance

A prototype with 100,000 cells, 30% of them hidden, 8 load prototypes each with a board stack of 30 boards and a sheet stack of 20 bands, at 1920×1080 in RTX Real-Time mode without a window, with the whole warehouse in view, and with the frame limiter and eco mode off:

| Case | Frames per second | Slowest frame |
|---|---|---|
| No changes | 282 | 8 ms |
| No changes, with 20 aisle lights | 285 | 6 ms |
| `invisibleIds` written in every frame | 39 | 32 ms |

**Limits of this prototype**: It had no racks and no cranes, and calculated no state, and was run only once. Feature 004's full scene reached 32 frames per second at this size. The numbers show that load prototypes and lights are not the main cost, but they do not prove SC-006. The performance tests do that, with the full scene.

## Real sizes and cells

- **Facts from the project owner**: Paper is 5.61 m by 2.08 m, one pallet to a cell, with its long side along the aisle. Boards are at most 5.6 m by 2.07 m, and can be split in two parts of at least 1.5 m that add up to 5.6 m.
- **Decision**: A new sample warehouse has cells 5.8 m long and 2.3 m wide, which are the loads' sizes with about 10 cm of space on each side. The height stays at the sample's 1.5 m until a real one is known. Existing samples and their results stay unchanged, and their articles get smaller types that fit a cell 3.2 m long and 1.5 m wide, as these samples only show the application.
- **Rationale**: Cell sizes change travel times, and so throughput. A separate warehouse file keeps this visible, and its results say nothing about the real warehouse until real cells are known.

## Fork sections under every possible part

- **Decision**: Sections stand at ± the larger of a quarter of a cell and half a cell less 0.85 m, instead of always at a quarter.
- **Rationale**: A cut can be anywhere, and the smallest part is 1.5 m. The outer 1.5 m at each end therefore always belongs to one part, so a section under this length carries its part wherever the cut is, and both sections together carry a whole unit. A section's tines reach about 0.54 m to either side in a 5.8 m cell, which stays inside this length.

## Open observation: the sky's color

Across windowless Kit runs with the same settings, the background was either gray or black for a whole run: 3 runs of the same recording gave gray once and black twice. This changes only the background, and its cause is not known. It may come from how the dome light starts up, and needs a look if it also appears with a window.

## Sharing prototypes between instancers

- **Result**: Each crane's carried load is a `PointInstancer` with one instance, using the prototypes under `/World/Loads`. Kit renders this, as seen in images of a pick and a set on the small sample, and no fallback is needed. Its cost has not been measured separately yet, which the performance tests do.
