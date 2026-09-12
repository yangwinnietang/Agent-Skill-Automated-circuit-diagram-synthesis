# Loaded voltage divider

![Loaded voltage divider](divider-loaded.svg)

[PDF](divider-loaded.pdf) · [PNG](divider-loaded.png) · [Editable TeX](divider-loaded.tex) · [Connections](divider-loaded.connections.md) · [JSON specification](../../../assets/verified-circuits/divider-loaded.json) · [Simulation report](divider-loaded.simulation/report.json)

Generated from one terminal model shared by the drawing and SPICE exporter. Expected values come from the [independent analytic reference](../../validation/analytic-reference.md). Voltage measurements use V(positive, negative); AC values are complex volts.

| Analysis | Measurement | Expected (V) | ngspice (V) | Absolute error (V) | Result |
|---|---|---:|---:|---:|---|
| DC | V_vcc | 5 | 5 | 0 | PASS |
| DC | V_out | 1.666666667 | 1.666666667 | 2.22e-16 | PASS |
| DC | output | 1.666666667 | 1.666666667 | 2.22e-16 | PASS |

All node voltages are checked. The `output` measurement can be differential; for the RLC example it is the voltage across R, not a node-to-ground voltage.

Model assumptions:

- The 10 kOhm load is parallel to the lower 10 kOhm resistor.
- The effective lower resistance is 5 kOhm; Vout = 1.666666667 V.

Raw simulator output, each netlist, and process logs are retained beside the JSON report. Rendering and these ideal-model comparisons do not certify component ratings, PCB connectivity, or physical circuit performance.
