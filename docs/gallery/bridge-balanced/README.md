# Balanced Wheatstone bridge

![Balanced Wheatstone bridge](bridge-balanced.svg)

[PDF](bridge-balanced.pdf) · [PNG](bridge-balanced.png) · [Editable TeX](bridge-balanced.tex) · [Connections](bridge-balanced.connections.md) · [JSON specification](../../../assets/verified-circuits/bridge-balanced.json) · [Simulation report](bridge-balanced.simulation/report.json)

Generated from one terminal model shared by the drawing and SPICE exporter. Expected values come from the [independent analytic reference](../../validation/analytic-reference.md). Voltage measurements use V(positive, negative); AC values are complex volts.

| Analysis | Measurement | Expected (V) | ngspice (V) | Absolute error (V) | Result |
|---|---|---:|---:|---:|---|
| DC | V_vcc | 5 | 5 | 0 | PASS |
| DC | V_left | 3.333333333 | 3.333333333 | 4.44e-16 | PASS |
| DC | V_right | 3.333333333 | 3.333333333 | 4.44e-16 | PASS |
| DC | output | 0 | -8.881784197e-16 | 8.88e-16 | PASS |

All node voltages are checked. The `output` measurement can be differential; for the RLC example it is the voltage across R, not a node-to-ground voltage.

Model assumptions:

- Vout = VL - VR. Both midpoints are 3.333333333 V, so Vout = 0 V.
- The 10 kOhm bridge remains connected; its ideal DC current is zero.

Raw simulator output, each netlist, and process logs are retained beside the JSON report. Rendering and these ideal-model comparisons do not certify component ratings, PCB connectivity, or physical circuit performance.
