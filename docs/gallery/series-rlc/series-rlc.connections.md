# Series RLC, output across resistor

| Device | Model / SI value | Ordered terminals |
|---|---|---|
| V1 | 1; AC=1 | +: `vin`, -: `0` |
| R1 | 100 | 1: `vin`, 2: `rl` |
| L1 | 0.01 | 1: `rl`, 2: `lc` |
| C1 | 1e-06 | 1: `lc`, 2: `0` |

Current is positive from the first to the second source terminal. Voltage is positive at the first voltage-source terminal. An opamp is a signal-only VCVS referenced to net `0`.

Measurements:

- `V_vin` = V(`vin`, `0`).
- `V_rl` = V(`rl`, `0`).
- `V_lc` = V(`lc`, `0`).
- `output` = V(`vin`, `rl`).

Model assumptions:

- Vout is the differential voltage across R1: V(vin) - V(rl), with positive polarity toward the source.
- The sequence is source to R1 to L1 to C1 to ground. No single node-to-ground voltage is Vout.
- Ideal band-pass response: resonance = 1591.549431 Hz and Q = 1. Source: DC 1 V and AC 1 V.
