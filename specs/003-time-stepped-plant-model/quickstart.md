# Quickstart: Time-Stepped Plant Model

Validation scenarios for this feature. Run all commands from the repository root. Commands, outputs, and signals are defined in [contracts/](contracts/).

## Prerequisites

```text
uv sync
uv run playwright install chromium
```

Chromium is needed only for S6.

## S1: Run a warehouse cycle by cycle (User Story 1)

```text
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/stepped --time-stepped
```

**Expected**: Exit code 0, with `report.md`, `result.json`, and `orders.csv` in `out/stepped`. `result.json` has `run.execution` with mode `time_stepped`, cycle time 50, the built-in controller, and signal list version 1, plus an empty `faults` list.

## S2: Reproducibility (User Story 1, SC-002)

Run S1 again to `out/stepped-2`.

**Expected**: All files in both directories are byte-identical.

## S3: Compare with the event-based simulation (User Story 2, SC-004)

```text
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/event
uv run highbay-sim compare out/event out/stepped
```

**Expected**: Exit code 0. Each `throughput_per_hour` value deviates by at most 1%, or by one completed order. Repeat with `--cycle-ms 5`, and the limit still holds.

## S4: Event-based results are unchanged (SC-009)

```text
uv run pytest tests/integration/test_reference_results.py
```

**Expected**: All pass, against hashes recorded before `engine.py` was changed.

## S5: Replace the controller, and read the signals (User Story 3, SC-007, SC-008)

```text
uv run highbay-sim run samples/verification/v1-warehouse.yaml samples/verification/v1-scenario.yaml --output out/scripted --time-stepped --controller tests/data/scripted_controller.py:ScriptedController --record-signals
uv run pytest tests/unit/test_plant_faults.py
```

**Expected**: The storage and retrieval complete with no change to the plant. `result.json` names the controller with its hash. `signals.csv` shows the job, the axis starts, the positions, and the load sensor. All fault tests pass. Without `--record-signals`, the other files are byte-identical.

`signals.csv` can reach about 100 MB per simulated hour at the planning target, so use recording for short runs.

## S6: Replay in 3D (User Story 4, SC-006)

```text
uv run highbay-sim run samples/replay/overloaded-warehouse.yaml samples/replay/busy-scenario.yaml --output out/stepped-view --time-stepped --replay
uv run highbay-sim view out/stepped-view
```

**Expected**: The viewer behaves as for an event-based run. The automated check is `tests/viewer/test_stepped_replay.py`.

## S7: Invalid settings (edge cases)

```text
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/bad --time-stepped --cycle-ms 0
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/bad --cycle-ms 50
uv run highbay-sim run samples/small-warehouse.yaml samples/daily-scenario.yaml --output out/bad --time-stepped --controller missing.py:Nothing
```

**Expected**: Each exits with code 2 and a message naming the problem, and no result files are written.

## S8: Performance (SC-005)

```text
uv run pytest tests/performance/test_stepped_performance.py -m performance
```

**Expected**: One simulated hour at the planning target in under 60 seconds. A pass applies to the machine running the test.
