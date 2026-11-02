# Highbay Replay extension

Replays a recorded warehouse run in Omniverse Kit. See [the application contract](../../../specs/004-omniverse-run-replay/contracts/application.md) for its controls, and [the state interface](../../../specs/004-omniverse-run-replay/contracts/state-interface.md) for connecting another source.

## Replacing a look

Each object type has a simple shape from `highbay/replay/appearance.py`. To use a detailed model for a type, give a USD file for it when starting the application:

```text
omniverse/run-replay.ps1 out/small --/exts/highbay.replay/looks/crane_mast=C:\models\mast.usd
```

The setting can also go in `omniverse/highbay.replay.app.kit`.

| Type | Object | Origin of the file |
|---|---|---|
| `crane_mast` | The crane's mast | The mast's center |
| `crane_carriage` | The platform that moves up the mast | The platform's center |
| `load_unit` | A load unit, stored or carried | The load unit's center |
| `rack_upright` | An upright of a rack | The upright's center |
| `rack_beam` | A beam of a rack | The beam's center |
| `transfer_point` | The marker at an aisle end | The marker's center |

The file needs a default prim, in meters, with Y up, and at the real size, as the simple shape's scale is not applied to it. Positions and behavior do not change.

Colors reach a model through the `primvars:displayColor` of its top prim, which its parts inherit if they have no color of their own. A material in the model takes the place of those colors.

If a file cannot be loaded, the simple shape is used, and a warning in Kit's console names the type.
