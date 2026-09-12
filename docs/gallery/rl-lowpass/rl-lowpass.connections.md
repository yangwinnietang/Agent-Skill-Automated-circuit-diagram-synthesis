# RL low-pass, output across series resistor

| Device | Model / SI value | Ordered terminals |
|---|---|---|
| V1 | 1; AC=1 | +: `vin`, -: `0` |
| L1 | 0.01 | 1: `vin`, 2: `out` |
| R1 | 100 | 1: `out`, 2: `0` |

Current is positive from the first to the second source terminal. Voltage is positive at the first voltage-source terminal. An opamp is a signal-only VCVS referenced to net `0`.

Measurements:

- `V_vin` = V(`vin`, `0`).
- `V_out` = V(`out`, `0`).
- `output` = V(`out`, `0`).

Model assumptions:

- Topology: source to inductor to resistor to ground. Vout is across the grounded resistor.
- Ideal components and no external output load. Source: DC 1 V and AC 1 V.
- Corner frequency = 1591.549431 Hz; expected AC values are also the voltage gain.
