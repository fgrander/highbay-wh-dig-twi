# Contract: Command Line

All of these need the extra: `uv sync --extra plc`, except `plc-source`. Without the extra, a command that needs it stops with exit code for invalid input and a message that says how to install it.

## Generate the source files

```text
highbay-sim plc-source WAREHOUSE.yaml --output DIR [--overwrite] [--cycle-ms N]
```

Writes `HB_Types.udt`, `HB_Interface.db`, and `HB_Control.scl`. The same warehouse, cycle time, and software version give identical files. It needs no connection.

## Run under PLC control

```text
highbay-sim run WAREHOUSE.yaml SCENARIO.yaml --output DIR --time-stepped --plc-host HOST [--plc-tls-ca FILE] [--cycle-ms N]
```

| Option | Meaning |
|---|---|
| `--plc-host HOST` | Address of the simulated PLC. Needs `--time-stepped`, and cannot be used with `--controller` |
| `--plc-tls-ca FILE` | Certificate to verify the PLC with. Without it, TLS is used if the PLC offers it, with no verification |

The password, if any, comes only from the environment variable `HIGHBAY_PLC_PASSWORD`. No option takes a password. Addresses and passwords are not written to the outputs or to logs, and the device string is.

A run takes as long in real time as it simulates. Ctrl+C ends it as a stopped run, and keeps what was recorded.

## Measure the exchange

```text
highbay-sim plc-measure WAREHOUSE.yaml --plc-host HOST [--plc-tls-ca FILE] [--cycle-ms N] [--seconds N]
```

It runs the steps of the start of a run, then exchanges signals in cycles with no plant and no jobs, for 60 seconds by default. It prints exchange time as median, 99th percentile, and slowest, and the number of overruns.

## Added output

A PLC run adds this section to `result.json`, with the same facts in the report. A run with no PLC does not have it, and is otherwise unchanged.

```json
"plc": {
  "device": "1;6ES7 SIM-01500-APLC;S4.1",
  "interface_version": 1,
  "reproducible": false,
  "stop_reason": "finished",
  "stopped_at_cycle": null,
  "cycles": 12000,
  "overrun_cycles": 3,
  "slowest_exchange_ms": 61.2,
  "simulated_s": 600.0,
  "real_s": 600.4
}
```

If a run stops during the warm-up, the section also holds `"warmup_skipped": true`, and the metrics cover all that was simulated.

## Exit codes

The existing codes apply. A refused device, a differing interface, a failed connection, and a PLC not in RUN count as invalid input. A run that stops early writes its outputs, and then ends with the failure code. This includes `interrupted`, since the results are not of the whole scenario.
