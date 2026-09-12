# Parallel resistors with upward current source

| Device | Model / SI value | Ordered terminals |
|---|---|---|
| I1 | 0.003 | from: `0`, to: `out` |
| R1 | 1000 | 1: `out`, 2: `0` |
| R2 | 2000 | 1: `out`, 2: `0` |

Current is positive from the first to the second source terminal. Voltage is positive at the first voltage-source terminal. An opamp is a signal-only VCVS referenced to net `0`.

Measurements:

- `V_out` = V(`out`, `0`).
- `output` = V(`out`, `0`).

Model assumptions:

- The current-source arrow points upward, from ground into the shared top node.
- Vout = 2 V; resistor currents are 2 mA through R1 and 1 mA through R2.
