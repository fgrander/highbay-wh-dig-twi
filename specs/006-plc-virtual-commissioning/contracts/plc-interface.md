# Contract: PLC Interface

**Interface version**: 1, for signal list version 1

This is how the [signal list](../../003-time-stepped-plant-model/contracts/signal-list.md) appears in the PLC. The signal list stays the only definition of what each signal means, and it does not change. A test checks this contract against the code and the generated files.

## Blocks

| Block | Kind | Content |
|---|---|---|
| `HB_CraneSignals` | User type | All signals of one crane |
| `HB_Interface` | Optimized global data block | The header, and `crane_1` to `crane_N` |
| `HB_CraneControl` | Function block | The control of one crane |
| `HB_Main` | Program cycle OB | Heartbeat, reset, and one call of `HB_CraneControl` per crane |

`N` is the number of aisles of the warehouse. Aisle `a` is `crane_a`.

## Types

| Signal list type | PLC type |
|---|---|
| number | `LReal` |
| integer | `DInt` |
| boolean, and boolean with rising edge | `Bool` |

Each signal keeps its name from the signal list, for example `HB_Interface.crane_1.horizontal_actual_m`.

## Header

These are about the connection, not the plant, and so they are not part of the signal list.

| Tag | Type | Written by | Meaning |
|---|---|---|---|
| `HB_Interface.interface_version` | `DInt` | start value | Must be 1 |
| `HB_Interface.signal_list_version` | `DInt` | start value | Must equal the model's version |
| `HB_Interface.crane_count` | `DInt` | start value | Must equal the warehouse's number of aisles |
| `HB_Interface.plc_heartbeat` | `DInt` | PLC | Counts up with each scan |
| `HB_Interface.reset_request` | `Bool` | model | While true, the PLC clears its commands, `job_done_id`, and states |
| `HB_Interface.reset_done` | `Bool` | PLC | True while `reset_request` is true and the reset is complete |

## Who writes what

| Signal list direction | Written by |
|---|---|
| Order handling to controller | model |
| Plant to controller | model |
| Controller to order handling | PLC |
| Controller to plant | PLC |

The model must never write a tag that belongs to the PLC, and a test checks this.

## Start of a run

Each step must succeed before the next, and any failure ends the run with a message and with no later step.

1. Connect, and read the device string. Refuse unless it holds an order number starting with `6ES7 SIM-`. **Nothing has been written up to here.**
2. Read the CPU state. Refuse unless it is RUN.
3. Check that every tag of this contract exists with the right type, and that the three start values match. List all differences.
4. Check that `plc_heartbeat` changes within 2 s.
5. Set `reset_request`, write starting values of all model tags, wait for `reset_done` for up to 5 s, then clear `reset_request`.

## Each cycle

1. Write the model's tags that changed since the last write. If `job_id` of a crane changed, write it afterwards in a request of its own.
2. Read all tags that the PLC writes, and `plc_heartbeat`.
3. Put the values in the crane's signals, for the plant to act on.
4. Wait for the cycle's deadline, or count an overrun.

## Rules for the PLC program

- A new `job_id` means that the job data is complete. The program copies it at that moment.
- Targets and the side are set one cycle before their start signal, as a read of many tags may not be consistent within one PLC scan.
- A start signal stays true for the hold time, then false for the hold time. Status is judged only after that.
- The hold time is 3 cycles, as a constant in the generated program.
- It uses the same sequence as the built-in controller. While `fault_code` is not 0, it starts nothing new. It sets `fault_reset` only if asked to in a later version.

## End of a run

The run ends with a stop reason, keeping what was recorded:

| Reason | When |
|---|---|
| `finished` | The run reached its duration |
| `connection_lost` | A read or write failed |
| `plc_not_running` | `plc_heartbeat` has not changed for 2 s |
| `interrupted` | The user pressed Ctrl+C |

When a run ends, the model clears nothing, and writes nothing more.

## Changes

Any change to these names, types, or steps requires a new interface version.
