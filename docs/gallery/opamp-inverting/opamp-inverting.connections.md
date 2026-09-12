# Inverting amplifier

| Device | Model / SI value | Ordered terminals |
|---|---|---|
| U1 | VCVS, A=1000000.0 | +: `0`, -: `sum`, out: `out` |
| V1 | 0.1 | +: `vin`, -: `0` |
| Rin | 10000 | 1: `vin`, 2: `sum` |
| Rf | 100000 | 1: `sum`, 2: `out` |

Current is positive from the first to the second source terminal. Voltage is positive at the first voltage-source terminal. An opamp is a signal-only VCVS referenced to net `0`.

Measurements:

- `V_vin` = V(`vin`, `0`).
- `V_sum` = V(`sum`, `0`).
- `V_out` = V(`out`, `0`).
- `output` = V(`out`, `0`).

Model assumptions:

- Signal-only ideal opamp: supply pins are intentionally omitted. SPICE uses Vout = 1e6 times (Vplus - Vminus).
- Infinite-gain result: Vout = -10 Vin = -1 V. The finite-gain check expects -0.999989000121 V.
- This model has no saturation, bandwidth, slew-rate, or output-current limits.
