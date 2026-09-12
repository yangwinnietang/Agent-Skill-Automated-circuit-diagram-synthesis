# Balanced Wheatstone bridge

| Device | Model / SI value | Ordered terminals |
|---|---|---|
| V1 | 5 | +: `vcc`, -: `0` |
| Rtl | 1000 | 1: `vcc`, 2: `left` |
| Rbl | 2000 | 1: `left`, 2: `0` |
| Rtr | 1500 | 1: `vcc`, 2: `right` |
| Rbr | 3000 | 1: `right`, 2: `0` |
| Rbridge | 10000 | 1: `left`, 2: `right` |

Current is positive from the first to the second source terminal. Voltage is positive at the first voltage-source terminal. An opamp is a signal-only VCVS referenced to net `0`.

Measurements:

- `V_vcc` = V(`vcc`, `0`).
- `V_left` = V(`left`, `0`).
- `V_right` = V(`right`, `0`).
- `output` = V(`left`, `right`).

Model assumptions:

- Vout = VL - VR. Both midpoints are 3.333333333 V, so Vout = 0 V.
- The 10 kOhm bridge remains connected; its ideal DC current is zero.
