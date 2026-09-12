# Inverting amplifier

![Inverting amplifier](opamp-inverting.svg)

[PDF](opamp-inverting.pdf) · [PNG](opamp-inverting.png) · [Editable TeX](opamp-inverting.tex) · [Connections](opamp-inverting.connections.md) · [JSON specification](../../../assets/verified-circuits/opamp-inverting.json) · [Simulation report](opamp-inverting.simulation/report.json)

Generated from one terminal model shared by the drawing and SPICE exporter. Expected values come from the [independent analytic reference](../../validation/analytic-reference.md). Voltage measurements use V(positive, negative); AC values are complex volts.

| Analysis | Measurement | Expected (V) | ngspice (V) | Absolute error (V) | Result |
|---|---|---:|---:|---:|---|
| DC | V_vin | 0.1 | 0.1 | 0 | PASS |
| DC | V_sum | 9.999890001e-07 | 9.999890001e-07 | 2.12e-22 | PASS |
| DC | V_out | -0.9999890001 | -0.9999890001 | 2.22e-16 | PASS |
| DC | output | -0.9999890001 | -0.9999890001 | 2.22e-16 | PASS |

All node voltages are checked. The `output` measurement can be differential; for the RLC example it is the voltage across R, not a node-to-ground voltage.

Model assumptions:

- Signal-only ideal opamp: supply pins are intentionally omitted. SPICE uses Vout = 1e6 times (Vplus - Vminus).
- Infinite-gain result: Vout = -10 Vin = -1 V. The finite-gain check expects -0.999989000121 V.
- This model has no saturation, bandwidth, slew-rate, or output-current limits.

Raw simulator output, each netlist, and process logs are retained beside the JSON report. Rendering and these ideal-model comparisons do not certify component ratings, PCB connectivity, or physical circuit performance.
