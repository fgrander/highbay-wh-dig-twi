# Data Model: Omniverse Crane and Load Models

Axes as in feature 004: x along the aisle, y up, z across it, with rack 1 at −z. All sizes are in meters.

## HandlingStep (state interface)

One handling step of a crane, from a recording.

| Field | Type | Rule |
|---|---|---|
| `kind` | `pick` or `set` | From the `load_picked` or `load_set` event that ends the step |
| `location` | Location or None | The event's location. None means an aisle end, where the forks stay at rest |
| `start_s` | float | The start of the `handling` activity |
| `end_s` | float | The end of the activity, which equals the event's time |

`CraneState.handling` holds the current step, or None outside one, and for sources that do not give it.

## ForkPose (derived)

The result of a pure function of a `HandlingStep`, a time, and the layout.

| Field | Meaning |
|---|---|
| `extension_m` | Signed distance of the forks from the crane's center along z. Negative towards rack 1 |
| `load_offset_m` | Signed distance of the load from the crane's center along z |
| `load_on_crane` | Whether the carried load is what shows the load |
| `hidden_cell` | The cell whose stored load is hidden meanwhile, or None |

With reach = the distance from the aisle's center to the rack's center, and share = (time − start) / (end − start):

| Share | Forks | Pick: load | Set: load |
|---|---|---|---|
| 0 to 0.4 | From 0 to reach | At the cell | Moves with the forks |
| 0.4 to 0.6 | At reach | At the cell | At the cell |
| 0.6 to 1 | From reach to 0 | Moves with the forks | At the cell, forks leave empty |

During a pick, `hidden_cell` is the cell for the whole step. At its end, the recording's event takes over. During a set, the load is still carried in the recording, and the event stores it. At an aisle end, or with no step, all offsets are 0.

The fork stages follow the sections: for an extension of d, `Top` is at d and `Middle` at d / 2. `Section1` and `Section2` always get the same values in this feature.

## CraneDimensions (derived)

Computed from the layout, and the only source of crane sizes for both the model and selection.

| Value | Rule |
|---|---|
| Column position | ± (cell length / 2 + clearance + column width / 2), so that any load that fits a cell fits between the carriage's end frames |
| Section position | ± the larger of cell length / 4 and cell length / 2 − 0.85 m. At 5.8 m this is 2.05 m, under the outer 1.5 m of a 5.6 m load, which every part of a split stack covers wherever the cut is |
| Fork top | The bottom of a stored load above the cell's floor, (1 − 0.85) / 2 × cell height |
| Fork bottom | Half a rack member above the cell's floor, plus a gap of 5 mm. If this leaves forks thinner than 2 cm, it moves down until they are 2 cm thick, and they may then touch the beam in that warehouse |
| Reach | (aisle width + cell width) / 2 |

Other values are fixed placeholders in the module, listed in the extension's README.

`crane_boxes(aisle, position, pose, carrying)` returns boxes for selection: columns, travel gear, top beam, carriage ends, forks at the pose's extension, and the load at its offset.

## LoadUnitType (data)

| Field | Type | Rule |
|---|---|---|
| `kind` | `board_stack`, `paper_pallet`, or `file` | Required |
| `length_m`, `width_m` | float | Above 0. Length runs along the aisle. For a type that can be split, this is the whole stack |
| `smallest_part_m` | float | Above 0, for `board_stack`. Optional, and without it the type cannot be split |
| `count` | int | Above 0, for the stack kinds |
| `thickness_m` | float | Above 0, for the stack kinds. The stack's height is `count` × `thickness_m` |
| `pallet_height_m` | float | Above 0, for `paper_pallet`, and added to the stack's height |
| `color`, `edge_color` | `#rrggbb` | Optional, for the stack kinds |
| `file` | path | For `file`. Relative paths start at the definitions file's folder |
| `height_m` | float | Above 0, for `file` |

A file must meet the rules for looks in the extension's README, with its origin on the floor, at the center of the unit.

## LoadDefinition (data)

| Field | Type | Rule |
|---|---|---|
| Article name | string | Must match a name in the recording's `articles` to have an effect |
| Units | one or two entries | Each has a `type`, and two entries are the parts of a split stack, each with a `length_m` |

One unit is centered in the cell, over both sections. Two parts lie end to end along the aisle, centered together with a cut of 1 cm between them, the first at −x over `Section1`, and the second at +x over `Section2`. A part's position follows from its length, so a cut can be anywhere.

## Warnings

All are collected when a run is opened, shown in the window, and never stop a run from opening. Each is shown once.

| Case | Result |
|---|---|
| The definitions file is missing or cannot be read | Warning with file and reason, and all articles look simple |
| A type's content breaks a rule above | Warning with the type, which is treated as unknown |
| A load names an unknown type | Warning with article and type, and that side looks simple |
| A file cannot be loaded | Warning with type and file, and that side looks simple |
| An article of the run has no load | Warning with the article, and it looks simple |
| A load is longer or wider than a cell, or higher than the space in it | Warning with article and size, and it shows as defined |
| A split's parts do not add up to the type's length, or one is below `smallest_part_m`, or the type cannot be split | Warning with article and lengths, and it shows as defined |

A load definition for an article that is not in the run is not a warning, so that one file can serve many runs.

## Scene

Changes to the scene in feature 004, with detailed models:

| Path | Content |
|---|---|
| `/World/AisleLights/Aisle_<n>` | The light of one aisle |
| `/World/Loads/Load_<i>` | A prototype: a group with the child `Unit1`, and `Unit2` for a split stack, with its origin at a cell's center |
| `/World/Cranes/Aisle_<n>/Mast` | The generated crane columns, copied into the root layer |
| `/World/Cranes/Aisle_<n>/Carriage/Platform/Section<k>/<Middle or Top>` | The moving fork stages |
| `/World/Cranes/Aisle_<n>/Carriage/CarriedLoad` | A `PointInstancer` with one instance, using the prototypes of `/World/Loads`. Its position gives the load's offset |

Prototypes for undefined articles are one simple box in the article's color, one per color in feature 004's sequence. With simple models, the scene stays as in feature 004.

The attributes of the fork stages are written as attribute specs, as for other per-frame values. If a file replaces the carriage and has no such stages, the forks do not move, and the load's offset stays 0.

### Selection outline

With detailed models, the outline of a selected crane or carried load surrounds the load space: a cell-sized box whose floor is at the carriage's height, so its center is half a cell's height above the recorded position.

### Stored instances

An instance is hidden if the source says that its cell is empty, or if a crane's pose names it as `hidden_cell`. The arrays are written only if the result differs from what was last written.
