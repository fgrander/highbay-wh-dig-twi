# Contract: State Interface Changes

**Interface version**: 2. This extends [version 1](../../004-omniverse-run-replay/contracts/state-interface.md), and everything there stays valid.

## Added

`CraneState` gets one optional field:

| Field | Type | Meaning |
|---|---|---|
| `handling` | `HandlingStep` or None | The handling step that the crane is in now, as in [data-model.md](../data-model.md). None outside a step, and always None from a source that does not know such steps. |

It defaults to None, so a source written for version 1 needs no change, and its forks stay at rest.

## Behavior

- `handling` depends only on the time and the data, like the rest of a run state.
- It does not change what the source reports. During a pick, `carrying` stays None and the cell stays occupied until the recorded event, so all figures and details stay as they were.
- `RecordedSource` raises `StateSourceError` when opening a recording if a `load_picked` or `load_set` event has no `handling` activity of its crane ending at the event's time.
