# Inverting weighted summer

| Device | Model / SI value | Ordered terminals |
|---|---|---|
| U1 | VCVS, A=1000000.0 | +: `0`, -: `sum`, out: `out` |
| Va | 0.2 | +: `va`, -: `0` |
| Vb | 0.4 | +: `vb`, -: `0` |
| Ra | 10000 | 1: `va`, 2: `sum` |
| Rb | 20000 | 1: `vb`, 2: `sum` |
| Rf | 10000 | 1: `sum`, 2: `out` |

Current is positive from the first to the second source terminal. Voltage is positive at the first voltage-source terminal. An opamp is a signal-only VCVS referenced to net `0`.

Measurements:

- `V_va` = V(`va`, `0`).
- `V_vb` = V(`vb`, `0`).
- `V_sum` = V(`sum`, `0`).
- `V_out` = V(`out`, `0`).
- `output` = V(`out`, `0`).

Model assumptions:

- Signal-only ideal opamp: supply pins are intentionally omitted. SPICE uses Vout = 1e6 times (Vplus - Vminus).
- Vout = -(Va + 0.5 Vb) = -0.4 V for infinite gain; the finite-gain check expects -0.399999000003 V.
- Ra and Rb meet only at the negative summing node. No saturation, bandwidth, or output-current limits are modeled.
