# Unloaded voltage divider

| Device | Model / SI value | Ordered terminals |
|---|---|---|
| V1 | 5 | +: `vcc`, -: `0` |
| Rtop | 10000 | 1: `vcc`, 2: `out` |
| Rbottom | 10000 | 1: `out`, 2: `0` |

Current is positive from the first to the second source terminal. Voltage is positive at the first voltage-source terminal. An opamp is a signal-only VCVS referenced to net `0`.

Measurements:

- `V_vcc` = V(`vcc`, `0`).
- `V_out` = V(`out`, `0`).
- `output` = V(`out`, `0`).

Model assumptions:

- Unloaded ideal divider: Vout = 5 V times 10 kOhm / 20 kOhm = 2.5 V.
