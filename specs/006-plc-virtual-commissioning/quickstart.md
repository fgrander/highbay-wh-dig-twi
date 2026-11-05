# Quickstart: PLC Virtual Commissioning

Commands are defined in [contracts/cli.md](contracts/cli.md).

## A. Without Siemens software

This shows the logic only. It does not show that the connection works with a real PLC.

```text
uv run pytest
uv run highbay-sim plc-source samples/small-warehouse.yaml --output out/plc-source
```

Expected: all tests pass, and three source files appear, with a set of signals for each crane. Generating again gives identical files.

## B. On S7-PLCSIM Advanced

These are manual steps, which have not been carried out yet. Expect to correct the generated files and these steps on the first pass.

Prerequisites, which the user installs and licenses: S7-PLCSIM Advanced and TIA Portal. See [research.md, R4](research.md) for the recommended versions.

1. In S7-PLCSIM Advanced, select communication over TCP/IP, and start an instance with an address reachable from this PC.
2. In TIA Portal, create a project with a CPU 1511-1 PN, firmware V2.9, with no password.
3. Add the three generated files as external sources, in this order: `HB_Types.udt`, `HB_Interface.db`, `HB_Control.scl`. Generate blocks from each, and compile.
4. Download to the instance, and set it to RUN.
5. Install the connection library, and try the connection:

   ```text
   uv sync --extra plc
   uv run highbay-sim plc-measure samples/small-warehouse.yaml --plc-host ADDRESS --seconds 60
   ```

   Expected: it names a device with `6ES7 SIM-`, and prints exchange times. **If the device is refused, stop here, and note the string that it reports**: research R3 then needs correcting.

6. Run a scenario under the PLC, and one with the built-in controller, then compare them:

   ```text
   uv run highbay-sim run samples/small-warehouse.yaml samples/plc-scenario.yaml --output out/plc --time-stepped --plc-host ADDRESS
   uv run highbay-sim run samples/small-warehouse.yaml samples/plc-scenario.yaml --output out/built-in --time-stepped
   uv run highbay-sim compare out/plc out/built-in
   ```

   A run takes as long in real time as it simulates, which is 10 minutes for this scenario.

   Expected: the same orders are finished, in a total time within 5% (SC-002), and `result.json` holds a `plc` section with `"reproducible": false`.

## C. Failure checks on S7-PLCSIM Advanced

| Action | Expected |
|---|---|
| Set the instance to STOP during a run | The run stops with `plc_not_running`, within about 2 s, and writes its outputs |
| Shut down the instance during a run | The run stops with `connection_lost`, and writes its outputs |
| Rename a tag in `HB_Interface`, and download | The run is refused before its first cycle, and names the tag |
| Start with the instance in STOP | The run is refused |

## D. Refusal of a real PLC

Do not test this on a real PLC connected to equipment. The automated tests cover it. If an isolated CPU is at hand, a run against it must be refused, with no write.
