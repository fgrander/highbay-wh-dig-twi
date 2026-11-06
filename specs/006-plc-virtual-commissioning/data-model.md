# Data Model: PLC Virtual Commissioning

No warehouse, scenario, or signal definition changes. These are additions. Names and types in the PLC are in [contracts/plc-interface.md](contracts/plc-interface.md).

## TagLink

The only way the rest of the feature reaches a PLC. The real one wraps `s7commplus`, and the test one is in memory.

| Member | Meaning |
|---|---|
| `device_string()` | The device string of the session, or nothing if unknown |
| `cpu_state()` | RUN, STOP, or unknown |
| `tag_types(names)` | The PLC type of each name, or nothing for a missing name |
| `read(names)` | The values, in order. Raises a link error on any failed item |
| `write(values)` | Writes in the given order. Raises a link error on any failed item. Never retries |
| `close()` | Ends the session |

## PlcConnection

Given from outside the repository (FR-012), and never recorded apart from what the contract allows.

| Field | Rule |
|---|---|
| `host` | Required, from the command line |
| `tls_ca` | Optional path, from the command line |
| `password` | Optional, only from the environment |

## PlcInterface

Derived from the signal list and the warehouse.

| Field | Rule |
|---|---|
| `crane_count` | The warehouse's number of aisles, at least 1 |
| `model_tags` | Names of tags written by the model, per crane |
| `plc_tags` | Names of tags written by the PLC, per crane |
| `header_tags` | Names and types of the header |

Every signal of `SIGNALS` belongs to exactly one of `model_tags` and `plc_tags`, by its direction.

## PlcController

A `Controller`, as in feature 003, so `stepped.py` does not need to know about PLCs. It holds the link, the interface, the last written values, and the cycle clock.

```text
created -> prepared (all steps of the start of a run passed) -> exchanging -> stopped
created -> refused (any step failed, and exchanging never starts)
```

A write can happen only in `prepared` or `exchanging`, and never before the identity check has passed. Being refused closes the link.

## PlcRunStats

| Field | Rule |
|---|---|
| `device` | The device string |
| `interface_version` | From the contract |
| `stop_reason` | `finished`, `connection_lost`, `plc_not_running`, or `interrupted` |
| `stopped_at_cycle` | The cycle, or nothing if `finished` |
| `cycles` | Number of exchanges |
| `overrun_cycles` | Number of cycles longer than the cycle time |
| `slowest_exchange_ms` | The slowest exchange |
| `simulated_s`, `real_s` | Simulated and elapsed time |

## ControllerStopped

A new exception that a controller raises to end a run early and keep its record, with a reason and a message. `SteppedRun` gains the optional stop information, which stays empty in all runs without a PLC. The record of a stopped run lasts as long as was simulated, and at least one cycle, so that metrics do not count time that was never simulated.

## PlcSourceFiles

The three generated texts, derived from `PlcInterface` and the cycle time. They hold the software version in a comment. They hold no date, so that they stay identical between runs.
