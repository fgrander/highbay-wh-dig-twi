# Implementation Plan: PLC Virtual Commissioning

**Branch**: `006-plc-virtual-commissioning` | **Date**: 2026-11-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-plc-virtual-commissioning/spec.md`

## Summary

A simulated S7-1500 CPU in S7-PLCSIM Advanced becomes the controller of the time-stepped plant model. The project generates the interface and a control program as source files for TIA Portal, and a new controller class exchanges the signal list with the PLC by symbolic name in each cycle. Before any write, the device must identify itself as simulated. All automated tests run with no Siemens software. Whether the connection works on a real instance, and how fast, stays open until the user has installed one.

The project owner approved the constitution amendment in [research.md](research.md) on 2026-11-05, and it is applied as version 1.1.0.

## Technical Context

**Language/Version**: Python 3.12 or newer, as in the existing project. SCL for the generated PLC program

**Primary Dependencies**: `s7commplus==0.3.0` as the optional extra `plc`, which brings in `cryptography`. Existing runs do not need it

**Storage**: Files only: the existing outputs, plus three generated source files

**Testing**: pytest, written test-first, with an in-memory `TagLink`, a stub client, and the library's in-memory server. Manual acceptance on S7-PLCSIM Advanced, by the quickstart

**Target Platform**: Windows 11. S7-PLCSIM Advanced with TCP/IP communication, on this PC or reachable from it

**Project Type**: Existing library and command-line interface

**Performance Goals**: One crane at a cycle of 50 ms, with at most 1% of cycles overrunning (SC-004). The only figure so far is the library's own cost on loopback, with a median of 1.5 ms by byte range, which says nothing about a real instance

**Constraints**: Results of all runs without a PLC stay identical (SC-006). No write before the identity check. No retried writes. No addresses or secrets in outputs, logs, or the repository

**Scale/Scope**: 23 signals per crane in each cycle. The library splits requests at 50 items or 900 bytes, so the number of cranes that hold a cycle must be measured

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Core independent of visualization | Pass | No visualization is touched |
| II. Reproducible simulation | Pass, by amendment 1.1.0 | A live PLC run follows real time, and cannot repeat exactly. Runs without a PLC are unchanged, and the report states it (FR-009) |
| III. Credible results | Pass | The report records the device, the overruns, and the elapsed time. Generated logic is compared with the built-in controller (SC-002) |
| IV. Live data as an option | Pass, by amendment 1.1.0 | Writes go to confirmed simulated PLCs only |
| V. Test-first | Pass | Tests first for the interface, the generator, the identity check, the exchange, and the stop handling |
| VI. Simplicity | Pass, with a justified dependency | One optional dependency, see Complexity Tracking. No change to the plant or to order handling |
| Credentials not committed | Pass | Host by option, password by environment only |
| Spec Kit sequence and own branch | Pass | |

**After Phase 1 design**: Same result. The design adds no new deviation. The design needs only one small change to `stepped.py`, for the early stop (R9).

## Project Structure

### Documentation (this feature)

```text
specs/006-plc-virtual-commissioning/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── plc-interface.md
│   └── cli.md
└── tasks.md
```

### Source Code (repository root)

```text
src/highbay_sim/
├── plc/
│   ├── __init__.py
│   ├── interface.py     # PlcInterface: tag names and types from the signal list
│   ├── source.py        # Generates the three source files
│   ├── link.py          # TagLink, its errors, and the value codec. No library import
│   ├── s7_link.py       # The only file that imports s7commplus
│   ├── controller.py    # PlcController: start of a run, exchange, clock, stats
│   └── measure.py       # plc-measure
├── stepped.py           # Changed: handles ControllerStopped
├── controller.py        # Changed: defines ControllerStopped
├── outputs.py           # Changed: the plc section, only for PLC runs
└── cli.py               # Changed: plc-source, plc-measure, --plc-host, --plc-tls-ca

tests/
├── data/                # In-memory PLC, with the control logic in Python
├── unit/                # Interface, generator, codec, identity check, exchange
└── integration/         # Whole runs through the in-memory PLC, and results unchanged without one
```

**Structure Decision**: A new `plc` package, so that the existing core does not depend on it. `s7commplus` is imported in `s7_link.py` alone, and only when a PLC is asked for (FR-013).

## Open Points to Confirm on the First Real Run

These cannot be settled here, and each has a safe outcome if the assumption is wrong:

1. The device string is as documented (R3). If not, the run is refused.
2. Named access works with the plain struct paths (R6). If not, the interface check reports it.
3. The exchange holds 50 ms (R7). If not, the overruns are reported, and the measured limit replaces SC-004.
4. The generated files compile (R10). If not, the generator is corrected.
5. How `--plc-tls-ca` is to be supplied for a PLCSIM certificate, and whether a run with no verification is accepted (R4).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Writing to a PLC (Principle IV) | The PLC cannot control a plant that it cannot read status from | Read-only would test nothing of the control program, and the user chose this role |
| A run tied to real time (Principle II) | The PLC runs in real time | Virtual time needs the .NET API, on the same machine, and is out of scope |
| New optional dependency (Principle VI) | Symbolic access to optimized blocks (FR-005) | python-snap7 cannot do it. Writing the protocol ourselves would be far larger |
