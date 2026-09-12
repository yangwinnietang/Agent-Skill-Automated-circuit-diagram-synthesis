# Independent electrical ground truth

All results below were calculated directly from Ohm’s law, Kirchhoff’s current law, and ideal impedance equations. No implementation or generated netlist from the circuit-diagram repository was used.

## Conventions and scope

- Node `0` is ground. `V(a,b)` means `V(a) − V(b)`; first terminal is positive for the measurement.
- For every two-terminal component, positive current flows from its first listed node to its second. A positive independent voltage source uses first terminal `+`, second terminal `−`. SPICE source current is negative when that source delivers power.
- A current source with node order `0 out` injects current upward from ground into `out`. Reversing that order changes the sign of the parallel-circuit result.
- Filter checks assume a voltage source declared `DC 1 AC 1` at zero AC phase. DC values therefore describe a 1 V input, and AC values equal the transfer function `H = Vout/Vin`.
- Capacitors are open and inductors are short in settled DC operating points. No initial conditions, parasitics, external output load, or instrument loading are included.
- Opamps are signal-only ideal models: infinite input impedance and zero output impedance, with power pins deliberately omitted. The SPICE element is a VCVS with finite gain `A = 1e6`: `E1 out 0 plus minus 1e6`. It enforces `Vout = A(Vplus − Vminus)`.
- Component counts include passives, independent sources, and the VCVS representing each opamp. Ground symbols, wires, node labels, and output probes do not count.
- Node names are canonical terminal specifications. Other names are equivalent if all terminal connectivity and measurement polarity are preserved.

## DC circuits and component counts

| Circuit | Electrical component count | Primary measurement | Expected result |
|---|---:|---|---:|
| Unloaded voltage divider | 3 (V×1, R×2) | `V(out,0)` | 2.5 V |
| Loaded voltage divider | 4 (V×1, R×3) | `V(out,0)` | 1.66666666667 V |
| Parallel resistors with upward current source | 3 (I×1, R×2) | `V(out,0)` | 2 V |
| Balanced Wheatstone bridge | 6 (V×1, R×5) | `V(left,right)` | 0 V |
| Unbalanced Wheatstone bridge | 6 (V×1, R×5) | `V(left,right)` | 0.413223140496 V |
| RC low-pass filter | 3 (V×1, R×1, C×1) | `V(out,0)` | 1 V |
| RC high-pass filter | 3 (V×1, C×1, R×1) | `V(out,0)` | 0 V |
| RL low-pass, output across series resistor | 3 (V×1, L×1, R×1) | `V(out,0)` | 1 V |
| Series RLC, output across resistor | 4 (V×1, R×1, L×1, C×1) | `V(vin,rl)` | 0 V |
| Inverting amplifier | 4 (V×1, R×2, E×1) | `V(out,0)` | ideal -1 V; A=1e6 -0.999989000121 V |
| Noninverting amplifier | 4 (V×1, R×2, E×1) | `V(out,0)` | ideal 1.1 V; A=1e6 1.09998790013 V |
| Inverting weighted summer | 6 (V×2, R×3, E×1) | `V(out,0)` | ideal -0.4 V; A=1e6 -0.399999000003 V |

## Canonical terminal maps

Each row below uses SPICE-compatible terminal order. Values are SI. For `E`, the four terminals are output positive, output negative, input positive, input negative. For filters, add `AC 1` to the voltage-source declaration.

### 1. Unloaded voltage divider

```spice
V1 vcc 0 5
Rtop vcc out 10000
Rbottom out 0 10000
```

Output: `V(out,0)`.

| DC node | Voltage (V) |
|---|---:|
| `vcc` | 5 |
| `out` | 2.5 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `Rtop` | 0.00025 |
| `Rbottom` | 0.00025 |
| `V1` | -0.00025 |

### 2. Loaded voltage divider

```spice
V1 vcc 0 5
Rtop vcc out 10000
Rbottom out 0 10000
Rload out 0 10000
```

Output: `V(out,0)`.

| DC node | Voltage (V) |
|---|---:|
| `vcc` | 5 |
| `out` | 1.66666666667 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `Rtop` | 0.000333333333333 |
| `Rbottom` | 0.000166666666667 |
| `Rload` | 0.000166666666667 |
| `V1` | -0.000333333333333 |

### 3. Parallel resistors with upward current source

```spice
I1 0 out 0.003
R1 out 0 1000
R2 out 0 2000
```

Output: `V(out,0)`.

| DC node | Voltage (V) |
|---|---:|
| `out` | 2 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `I1` | 0.003 |
| `R1` | 0.002 |
| `R2` | 0.001 |

### 4. Balanced Wheatstone bridge

```spice
V1 vcc 0 5
Rtl vcc left 1000
Rbl left 0 2000
Rtr vcc right 1500
Rbr right 0 3000
Rbridge left right 10000
```

Output: `V(left,right)`.

| DC node | Voltage (V) |
|---|---:|
| `vcc` | 5 |
| `left` | 3.33333333333 |
| `right` | 3.33333333333 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `Rtl` | 0.00166666666667 |
| `Rbl` | 0.00166666666667 |
| `Rtr` | 0.00111111111111 |
| `Rbr` | 0.00111111111111 |
| `Rbridge` | 0 |
| `V1` | -0.00277777777778 |

### 5. Unbalanced Wheatstone bridge

```spice
V1 vcc 0 5
Rtl vcc left 1000
Rbl left 0 2000
Rtr vcc right 1500
Rbr right 0 2000
Rbridge left right 10000
```

Output: `V(left,right)`.

| DC node | Voltage (V) |
|---|---:|
| `vcc` | 5 |
| `left` | 3.30578512397 |
| `right` | 2.89256198347 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `Rtl` | 0.00169421487603 |
| `Rbl` | 0.00165289256198 |
| `Rtr` | 0.00140495867769 |
| `Rbr` | 0.00144628099174 |
| `Rbridge` | 4.13223140496e-05 |
| `V1` | -0.00309917355372 |

### 6. RC low-pass filter

```spice
V1 vin 0 1
R1 vin out 1000
C1 out 0 1e-07
```

Output: `V(out,0)`.

| DC node | Voltage (V) |
|---|---:|
| `vin` | 1 |
| `out` | 1 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `V1` | 0 |
| `R1` | 0 |
| `C1` | 0 |

### 7. RC high-pass filter

```spice
V1 vin 0 1
C1 vin out 1e-07
R1 out 0 1000
```

Output: `V(out,0)`.

| DC node | Voltage (V) |
|---|---:|
| `vin` | 1 |
| `out` | 0 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `V1` | 0 |
| `R1` | 0 |
| `C1` | 0 |

### 8. RL low-pass, output across series resistor

```spice
V1 vin 0 1
L1 vin out 0.01
R1 out 0 100
```

Output: `V(out,0)`.

| DC node | Voltage (V) |
|---|---:|
| `vin` | 1 |
| `out` | 1 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `V1` | -0.01 |
| `R1` | 0.01 |
| `L1` | 0.01 |

### 9. Series RLC, output across resistor

```spice
V1 vin 0 1
R1 vin rl 100
L1 rl lc 0.01
C1 lc 0 1e-06
```

Output: `V(vin,rl)`.

| DC node | Voltage (V) |
|---|---:|
| `vin` | 1 |
| `rl` | 1 |
| `lc` | 1 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `V1` | 0 |
| `R1` | 0 |
| `L1` | 0 |
| `C1` | 0 |

### 10. Inverting amplifier

```spice
V1 vin 0 0.1
Rin vin sum 10000
Rf sum out 100000
E1 out 0 0 sum 1000000
```

Output: `V(out,0)`.

| DC node | Voltage (V) |
|---|---:|
| `vin` | 0.1 |
| `sum` | 9.99989000121e-07 |
| `out` | -0.999989000121 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `Rin` | 9.9999000011e-06 |
| `Rf` | 9.9999000011e-06 |
| `V1` | -9.9999000011e-06 |
| `E1` | 9.9999000011e-06 |

Ideal infinite-gain output: **-1 V**. Finite-gain formula: `-10*Vin / (1+11/A)`.

### 11. Noninverting amplifier

```spice
V1 vin 0 0.1
Rg sum 0 10000
Rf sum out 100000
E1 out 0 vin sum 1000000
```

Output: `V(out,0)`.

| DC node | Voltage (V) |
|---|---:|
| `vin` | 0.1 |
| `sum` | 0.0999989000121 |
| `out` | 1.09998790013 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `Rg` | 9.99989000121e-06 |
| `Rf` | -9.99989000121e-06 |
| `V1` | 0 |
| `E1` | -9.99989000121e-06 |

Ideal infinite-gain output: **1.1 V**. Finite-gain formula: `11*Vin / (1+11/A)`.

### 12. Inverting weighted summer

```spice
Va va 0 0.2
Vb vb 0 0.4
Ra va sum 10000
Rb vb sum 20000
Rf sum out 10000
E1 out 0 0 sum 1000000
```

Output: `V(out,0)`.

| DC node | Voltage (V) |
|---|---:|
| `va` | 0.2 |
| `vb` | 0.4 |
| `sum` | 3.99999000003e-07 |
| `out` | -0.399999000003 |

| Branch | DC current, first terminal → second (A) |
|---|---:|
| `Ra` | 1.99999600001e-05 |
| `Rb` | 1.99999800001e-05 |
| `Rf` | 3.99999400002e-05 |
| `Va` | -1.99999600001e-05 |
| `Vb` | -1.99999800001e-05 |
| `E1` | 3.99999400002e-05 |

Ideal infinite-gain output: **-0.4 V**. Finite-gain formula: `-(Va + 0.5*Vb) / (1+2.5/A)`.

## AC filter reference values

The two RC filters have `fc = 1/(2πRC)`. The RL low-pass has `fc = R/(2πL)`. The RLC resistor-output filter has `f0 = 1/(2π√(LC))` and `Q = √(L/C)/R = 1`. For these particular values, all four characteristic frequencies equal **1591.549430918953 Hz**.

Magnitude is a ratio (or volts for `AC 1`), dB means `20 log10 |H|`, and phase is the principal phase of output relative to input.

### RC low-pass filter

`H(jω) = 1 / (1 + j*w*R*C)`; output `V(out,0)`.

| Frequency (Hz) | Re(H) | Im(H) | Magnitude | Magnitude (dB) | Phase (°) |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.996067682407 | -0.0625847782706 | 0.998031904504 | -0.0171115043446 | -3.59527377987 |
| 1591.54943092 | 0.5 | -0.5 | 0.707106781187 | -3.01029995664 | -45 |
| 10000 | 0.0247045230319 | -0.155223096135 | 0.157176725478 | -16.0722352658 | -80.956938921 |

### RC high-pass filter

`H(jω) = j*w*R*C / (1 + j*w*R*C)`; output `V(out,0)`.

| Frequency (Hz) | Re(H) | Im(H) | Magnitude | Magnitude (dB) | Phase (°) |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.00393231759283 | 0.0625847782706 | 0.0627081939847 | -24.0535141372 | 86.4047262201 |
| 1591.54943092 | 0.5 | 0.5 | 0.707106781187 | -3.01029995664 | 45 |
| 10000 | 0.975295476968 | 0.155223096135 | 0.987570492151 | -0.108637898643 | 9.04306107904 |

### RL low-pass, output across series resistor

`H(jω) = R / (R + j*w*L)`; output `V(out,0)`.

| Frequency (Hz) | Re(H) | Im(H) | Magnitude | Magnitude (dB) | Phase (°) |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.996067682407 | -0.0625847782706 | 0.998031904504 | -0.0171115043446 | -3.59527377987 |
| 1591.54943092 | 0.5 | -0.5 | 0.707106781187 | -3.01029995664 | -45 |
| 10000 | 0.0247045230319 | -0.155223096135 | 0.157176725478 | -16.0722352658 | -80.956938921 |

### Series RLC, output across resistor

`H(jω) = R / (R + j*(w*L - 1/(w*C)))`; output `V(vin,rl)`.

| Frequency (Hz) | Re(H) | Im(H) | Magnitude | Magnitude (dB) | Phase (°) |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.00396342697114 | 0.0628308699429 | 0.0629557540749 | -24.0192913957 | 86.3905139901 |
| 1591.54943092 | 1 | -2.84217094304e-16 | 1 | 0 | -1.62844399691e-14 |
| 10000 | 0.0259714976991 | -0.15905024051 | 0.161156748848 | -15.8550300518 | -80.7259555716 |

## Topology and polarity checks

1. **Unloaded divider:** the two 10 kΩ resistors are in series; the midpoint is 2.5 V. There is no separate load.
2. **Loaded divider:** the added 10 kΩ load connects exactly between `out` and ground, parallel to the lower 10 kΩ resistor. The effective lower resistance is 5 kΩ, yielding 5/3 V.
3. **Parallel circuit:** both resistors connect across the same two nodes. The 3 mA source points from ground toward `out`; 2 mA flows downward through 1 kΩ and 1 mA through 2 kΩ. An arrow pointing down would produce −2 V.
4. **Balanced bridge:** `Rtl/Rbl = Rtr/Rbr = 1/2`. Both midpoints are 10/3 V. Bridge current is zero within numerical precision. The bridge resistor remains present, and is neither an open circuit nor a short.
5. **Unbalanced bridge:** the 10 kΩ bridge loads both divider legs. Solve the simultaneous node equations, rather than treating the legs as unloaded dividers. The expected bridge polarity is left positive: 0.413223140496 V, with 41.3223140496 µA left to right.
6. **RC low-pass:** resistor connects input to output; capacitor connects output to ground. Output tends to input at DC and to zero at high frequency.
7. **RC high-pass:** capacitor connects input to output; resistor connects output to ground. Output is zero at DC and tends to input at high frequency.
8. **RL low-pass:** use source → L → R → ground so that the resistor output is the single-ended junction voltage `V(out,0)`. This follows the clarified topology. If the components were drawn source → R → L → ground instead, the resistor output would require the differential input-minus-junction voltage; measuring that alternate junction to ground would give a high-pass response.
9. **Series RLC:** preserve source → R → L → C → ground. Output across R is `V(vin,rl)`, equivalently `V(vin)-V(rl)`. This is a band-pass response with unity magnitude and zero phase at resonance. No individual non-ground node voltage equals the requested output.
10. **Inverting amplifier:** signal resistor and feedback resistor both meet the negative input. Positive input connects to ground. Positive input signal yields a negative output.
11. **Noninverting amplifier:** signal source connects only to the positive input; `Rg` connects negative input to ground and `Rf` connects negative input to output. Positive input signal yields positive output.
12. **Summer:** inputs have separate sources and separate resistors, sharing only the negative summing node. Positive input is grounded. `Ra=10 kΩ`, `Rb=20 kΩ`, `Rf=10 kΩ`; contributions are −0.2 V each, totaling −0.4 V ideally.

## Derivations and checking limits

For either bridge, solve:

`(1/Rtl + 1/Rbl + 1/Rbridge) VL − VR/Rbridge = 5/Rtl`

`−VL/Rbridge + (1/Rtr + 1/Rbr + 1/Rbridge) VR = 5/Rtr`

This independent calculation satisfies KCL at both midpoints to below 1e−16 A in double precision. The unbalanced total supply current is 3.09917355372 mA; the balanced total is 2.77777777778 mA.

For a finite-gain inverting opamp, output is divided by `1 + noise_gain/A` relative to the infinite-gain result. Noise gain is 11 for the inverting and noninverting amplifiers, and 2.5 for the summer. Thus the finite-gain outputs are −0.999989000121 V, +1.09998790013 V, and −0.399999000003 V. The summing node is approximately 1.0 µV, 0.0999989 V, and 0.4 µV, respectively; “virtual ground” is an approximation in the two inverting examples.

The VCVS model has no supply rails, saturation, current limits, bandwidth, slew rate, offset, bias currents, or noise. It is suitable for these linear teaching checks and cannot predict a physical opamp’s large-signal behavior. Signal-only power omission should be stated on every such diagram or its accompanying metadata.

For a simulator check, compare against the finite-gain opamp values, not exactly against the infinite-gain outputs. A practical baseline tolerance is `1e−6` relative plus `1e−9` absolute for node voltages and complex gains, with absolute tolerance `1e−9` V for a balanced bridge output and `1e−12` A for its current. Tolerances may be relaxed if the simulator output is deliberately printed with fewer digits. Compare complex real/imaginary values directly to avoid phase wrapping and undefined phase at zero magnitude.

The only output-measurement ambiguity is “across R” when R floats above ground. The clarified RL map places R against ground; the RLC map resolves its floating R measurement with a differential expression. For SPICE dialects that do not accept `V(a,b)` in a particular measurement statement, use the algebraically identical `V(a)-V(b)`.

Machine-readable values and terminal maps are in `electrical-ground-truth.json`.
