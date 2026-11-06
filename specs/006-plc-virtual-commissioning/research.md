# Research: PLC Virtual Commissioning

Checked on 2026-11-05. "Probed" means run here with s7commplus 0.3.0 from PyPI, in a separate environment, against its own in-memory server. "Documented" means stated by the library's documentation or source, and not seen here. No Siemens software was available, so nothing here has been tried on a real S7-PLCSIM Advanced instance.

## R1: Connection library

**Decision**: Use `s7commplus`, pinned to the released 0.3.0, as an optional extra of the project, behind one adapter module.

**Rationale**:

- The user asked for python-snap7 from GitHub for symbolic access. python-snap7 3.3.1 cannot do that. Its documentation says that it reaches only non-optimized data blocks with PUT/GET enabled, and points to `s7commplus` for symbolic access.
- `s7commplus` addresses tags by name, including in optimized blocks. Its documentation lists S7-PLCSIM Advanced V8 with a CPU 1511-1 PN as validated for connecting, browsing, reading, and writing.
- It is young (first release September 2026) and unofficial, and its symbolic access is marked experimental. The adapter keeps it replaceable.

**Alternatives considered**:

- python-snap7 with a non-optimized block and fixed addresses: well proven, but goes against FR-005 and the user's wish.
- OPC UA: a standard interface with symbolic names, but needs a server set up in the CPU, and its speed is unmeasured. It stays the fallback if `s7commplus` proves unusable.
- The S7-PLCSIM Advanced API: can synchronize virtual time, but is .NET and works only on the same machine. Out of scope by the spec.

## R2: Released version or current GitHub state

**Decision**: Use the release, with `read_tags` and `write_tags` and a small codec of our own for the three types in use.

**Rationale**: The current documentation describes `read_values` and `write_values`, but 0.3.0 from PyPI does not have them (probed: `AttributeError`). The GitHub source has them, under the same version number 0.3.0. `read_tags` and `write_tags` are in the release, give one result per tag, and split large batches. A pinned release keeps `uv.lock` simple. If the typed calls are wanted later, they fit inside the adapter.

**Alternatives considered**: Pinning a GitHub commit, which the user's wording leans towards. It remains a one-line change if the real PLC shows a fault that only the newer code fixes.

## R3: Telling a simulated PLC from a real one (FR-006)

**Decision**: Read the device string of the session, and allow only an order number that starts with `6ES7 SIM-`. Anything else, including no string at all, is refused before the first write. Then check the interface block (R6), as a second barrier.

**Rationale**: The library's documentation says that S7-PLCSIM Advanced "reports itself rather than the project's CPU", as `1;6ES7 SIM-01500-APLC;S4.1` on V8.0, and that this was seen on V8.0 only.

**Limits**:

- This has not been seen here. It must be confirmed on the first real run, before the first write. An instance that reports otherwise is refused, so a wrong assumption fails safely, and stops the feature rather than endangering anything.
- The library has no public call for the string. The adapter uses `extract_session_version_string` on a private attribute of the connection. The exact version pin covers this, and a change makes the check refuse.
- `device_family` from the library does not help: its table lists `-VPLC` numbers, not `-APLC`.
- Probed: the in-memory server gives no usable identity, so it tests the refusal path.
- This guards against mistakes, not against a device that lies about itself.

## R4: Which Siemens versions to install

**Decision**: Recommend S7-PLCSIM Advanced V8 with the TIA Portal version that matches it, and a CPU 1511-1 PN with firmware V2.9 in an unprotected project, connected with TLS.

**Rationale**: That is the combination that the library documents as validated. Password login over TLS is documented as not working yet on it, so the project stays without a password. Which TIA Portal version matches V8, and whether the folder `Portal V17` on this PC is usable, must be checked against Siemens' compatibility list by the user. Other versions may work, but are untested by anyone that we know of.

## R5: Testing without Siemens software (FR-013)

**Decision**: Tests use an in-memory stand-in for the adapter's interface, with a Python copy of the generated control logic running asynchronously to the model. The real adapter is tested for its encoding and refusals against a stub client, and for connecting and refusal against the library's in-memory server.

**Rationale**: The spec assumed that the library's emulator could carry whole runs. It cannot: it is documented as serving only byte ranges of blocks, and it "does not execute a controller program". Probed: `browse` returns 0 variables, so named access has nothing to find. So a passing test suite does not show that the connection works on a real PLC. That is what the manual acceptance in the quickstart is for.

## R6: Shape of the interface in the PLC

**Decision**: One optimized global block `HB_Interface` with a header and one member `crane_N` of a user type per crane, so tag names look like `HB_Interface.crane_1.job_id`. Details are in [contracts/plc-interface.md](contracts/plc-interface.md).

**Rationale**: Plain struct paths avoid depending on how array indexes are written in names, since symbolic access is experimental. Numbers become LREAL, so that a position passes unchanged. Integers become DINT.

## R7: Timing and exchange

**Decision**: The exchange lives entirely in a new controller class, whose `scan` writes status, reads commands, and then waits for the next cycle's deadline by the real clock. `stepped.py` keeps its loop, and simulated time stays `cycle × cycle time`. A cycle that overruns is counted, and the next one starts at once. No cycle is skipped.

**Rationale**: The plant's physics stay exactly as they are, and the existing controller interface is the seam that feature 003 prepared. If the exchange is too slow, simulated time falls behind real time, which is reported, rather than the plant jumping.

**Further details**:

- Only changed values are written after the first cycle. Probed on loopback, writing 14 and reading 9 items by byte range took a median of 1.5 ms and at most 1.9 ms over 500 rounds. That is only the library's own cost. It says nothing about S7-PLCSIM Advanced, and named access may differ, which is why User Story 4 exists.
- The library splits batches over 50 items or 900 bytes, and a split write is not atomic. So `job_id` is written last, in its own request, whenever it changes, and the PLC treats a new `job_id` as the sign that the job data is complete.
- A heartbeat in the PLC, read in each cycle, shows a stopped or frozen PLC with no extra request. The library's `get_cpu_state` is used once at the start.

## R8: Edges across an unsynchronized link

**Decision**: The generated program holds each start signal true for a hold time, then false for the same time, and judges status only after that. The hold time is generated from the cycle time as 3 cycles, by default 150 ms.

**Rationale**: PLC scans and model cycles are not aligned. A start shorter than a cycle would be missed, and just after a start the PLC would still see `in_position` as true from before the plant reacted. Each step of a job is delayed by about this time compared with the built-in controller, which SC-002 allows for.

## R9: Keeping results when the connection is lost (FR-011)

**Decision**: Add one exception type, which `_Run.execute` catches to end the loop and return what was recorded, along with the stopping cycle and reason. Any other controller error behaves as before.

**Rationale**: At present any controller error discards the record. Runs without a PLC never raise the new type, so their results cannot change.

## R10: Importing into TIA Portal

**Decision**: Generate external source files: `HB_Types.udt`, `HB_Interface.db`, and `HB_Control.scl`, with the program in its own program cycle OB `HB_Main`, so that nothing existing needs editing.

**Limit**: The files can only be compared with expected text here. Whether they compile is known only after the first import, and they should be expected to need corrections then.

## Constitution amendment

Approved by the project owner on 2026-11-05, and applied as the MINOR change to 1.1.0. The wording as approved:

> Add to Principle II: "A run coupled to a live simulated PLC is exempt from this principle, because it follows real time. Its report MUST state that it is not reproducible."
>
> Replace the last sentence of the first paragraph of Principle IV with: "Live connections MUST be read-only towards real warehouse systems and real PLCs. Writing is allowed only to a simulated PLC, whose identity MUST be confirmed before the first write. Any device that cannot be confirmed as simulated MUST be refused. Any other write path requires a constitution amendment."
