# RC low-pass filter

![RC low-pass filter](rc-lowpass.svg)

[PDF](rc-lowpass.pdf) · [PNG](rc-lowpass.png) · [Editable TeX](rc-lowpass.tex) · [Connections](rc-lowpass.connections.md) · [JSON specification](../../../assets/verified-circuits/rc-lowpass.json) · [Simulation report](rc-lowpass.simulation/report.json)

Generated from one terminal model shared by the drawing and SPICE exporter. Expected values come from the [independent analytic reference](../../validation/analytic-reference.md). Voltage measurements use V(positive, negative); AC values are complex volts.

| Analysis | Measurement | Expected (V) | ngspice (V) | Absolute error (V) | Result |
|---|---|---:|---:|---:|---|
| DC | V_vin | 1 | 1 | 0 | PASS |
| DC | V_out | 1 | 1 | 0 | PASS |
| DC | output | 1 | 1 | 0 | PASS |
| AC 100 Hz | V_vin | 1 +0j | 1 +0j | 0 | PASS |
| AC 100 Hz | V_out | 0.9960676824 -0.06258477827j | 0.9960676824 -0.06258477827j | 1.39e-17 | PASS |
| AC 100 Hz | output | 0.9960676824 -0.06258477827j | 0.9960676824 -0.06258477827j | 1.39e-17 | PASS |
| AC 1591.54943 Hz | V_vin | 1 +0j | 1 +0j | 0 | PASS |
| AC 1591.54943 Hz | V_out | 0.5 -0.5j | 0.5 -0.5j | 0 | PASS |
| AC 1591.54943 Hz | output | 0.5 -0.5j | 0.5 -0.5j | 0 | PASS |
| AC 10000 Hz | V_vin | 1 +0j | 1 +0j | 0 | PASS |
| AC 10000 Hz | V_out | 0.02470452303 -0.1552230961j | 0.02470452303 -0.1552230961j | 5.59e-17 | PASS |
| AC 10000 Hz | output | 0.02470452303 -0.1552230961j | 0.02470452303 -0.1552230961j | 5.59e-17 | PASS |

All node voltages are checked. The `output` measurement can be differential; for the RLC example it is the voltage across R, not a node-to-ground voltage.

Model assumptions:

- The output is across the capacitor; low frequencies pass.
- Ideal components and no external output load. Source: DC 1 V and AC 1 V.
- Corner frequency = 1591.549431 Hz; expected AC values are also the voltage gain.

Raw simulator output, each netlist, and process logs are retained beside the JSON report. Rendering and these ideal-model comparisons do not certify component ratings, PCB connectivity, or physical circuit performance.
