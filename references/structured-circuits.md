# Structured circuits: one terminal model, two outputs

Use this route for linear teaching and analysis diagrams whose topology is already
known. The agent interprets text or an image and supplies the connections and
layout. The script is deterministic: it does not contain an LLM, OCR system, or
automatic layout engine. Freeform CircuiTikZ remains available for other devices.

## Quick start

```bash
python scripts/synthesize.py assets/verified-circuits/divider-loaded.json \
  --output-dir build/loaded --format svg --format png --verify
python scripts/electrical.py assets/verified-circuits/divider-loaded.json \
  --output-dir build/loaded-check --check-only
python scripts/build_gallery.py --output-dir build/gallery
```

`synthesize.py` generates `<id>.tex`, `<id>.connections.md` and `<id>.cir`.
`--format` requests real compilation; PDF is retained whenever compilation runs.
`--verify` creates `<id>.simulation/` containing every analysis netlist, ASCII raw
output, process log, and `report.json`. Without either flag, only source is
generated. The standalone `.cir` runs the first requested analysis; use the
simulation directory for the full set. No third-party Python package is required.

Existing generated output is protected. Use a new directory or explicitly pass
`--overwrite`. A failed render or verification preserves old deliverables and
saves failure evidence in a separate `failed-*` directory. Only a completed
successful command identifies current deliverables. Publication is atomic per
file; it is not a directory transaction. Use separate destinations for concurrent
jobs. The low-level `electrical.py` command replaces same-named analysis files and
writes a failing report when a simulator or comparison fails.

For Chinese port labels, use `--chinese --engine xelatex` with ctex/Fandol installed.
Text labels are escaped, not evaluated as TeX. Unicode labels still require a font
that contains the requested glyphs. Inspect the image after any layout change.

## Schema

The complete [unloaded divider](../assets/verified-circuits/divider-unloaded.json)
is a small runnable template; the [summer](../assets/verified-circuits/opamp-summer.json)
shows multi-pin anchors. Values use **numeric SI units**, such as `10000` ohms or
`1e-7` farads. Strings such as `"10k"`, nonfinite values, duplicate JSON keys, and
unknown fields are rejected.

| Field | Meaning |
|---|---|
| `id`, `title` | Safe output basename and descriptive title |
| `category`, `notes` | Optional grouping and explicit model assumptions |
| `nodes` | Drawing point IDs mapped to `{net, at: [x,y]}` or `{net, anchor}` |
| `components` | References, kinds, values and **ordered** point IDs for pins |
| `wires` | Point pairs joined by drawn wires; both must declare the same net |
| `grounds` | Point IDs carrying explicit ground symbols, all on net `0` |
| `junctions` | Branch-point IDs with connection dots |
| `ports` | `{point, label}` markers; labels do not create connectivity |
| `analysis` | `dc` Boolean, `ac_hz` frequencies, and named voltage measurements |
| `expected` | Independent `dc` values and complex `ac` values for each measurement |

Point IDs, component references, and measurement names start with an ASCII letter,
followed by letters, digits or underscores. The circuit ID also allows hyphens.
Net names are `0` or identifiers; names differing only by case are not distinct
SPICE nets. Reuse one spelling. A coordinate cannot be reused under another point
ID; reuse the existing point instead. References start with the device kind
(`R`, `C`, `L`, `V`, `I`), or `U` for an opamp.

```json
{"ref":"R1","kind":"R","value":10000,"pins":["TOP","MID"]}
```

| Kind | Ordered pins | Extra fields / model |
|---|---|---|
| `R`, `C`, `L` | First, second | Positive `value`; ideal passive |
| `V` | Positive, negative | DC `value`, optional real AC amplitude `ac` |
| `I` | Arrow from, arrow to | DC `value`, optional real AC amplitude `ac` |
| `opamp` | Plus, minus, output | Positive `gain`, center `at: [x,y]`; VCVS to ground |

An opamp's pin points use exact matching anchors, such as `U1.plus`, `U1.minus`,
and `U1.out`. The renderer translates them to actual CircuiTikZ pins; it never
connects a wire to the device center. The optional `label_side` is `above` or
`below` relative to the component path. The renderer draws voltage sources from
negative to positive with `V,invert`; inspect signs again if changing symbol
conventions or editing the resulting TeX.

All points sharing a named net must be connected through explicit wires. Multiple
explicit ground symbols can unify net `0`. A port is only a visual terminal, not
an off-sheet net connector. Wires involving an opamp anchor use a horizontal-then-
vertical elbow (`-|`), so their listed direction affects layout. Other wires and
two-terminal component paths are straight. Coordinate selection and image review
remain essential: this structural validator does not interpret geometric wire
crossings, device-body intersections, or label overlap.

## Measurements and independent expectations

```json
{
  "analysis": {
    "dc": true,
    "ac_hz": [100, 10000],
    "measurements": [{"name":"output","positive":"out","negative":"0"}]
  },
  "expected": {
    "dc": {"output":1},
    "ac": [
      {"frequency":100,"values":{"output":[0.9960676824071726,-0.0625847782705717]}},
      {"frequency":10000,"values":{"output":[0.024704523031857644,-0.15522309613464763]}}
    ]
  }
}
```

This fragment describes the 1 kΩ / 100 nF RC low-pass with `DC 1 AC 1` input.
Every declared measurement must have an expectation in every requested analysis.
At least one analysis and one voltage measurement are required. AC frequencies
must be positive, unique, and match the expected-frequency set exactly. Each
complex value is `[real, imaginary]` in volts; it equals gain only for a 1 V AC
input. AC amplitude has zero phase, or the equivalent sign reversal if negative.

Use `positive: "vin", negative: "rl"` for the RLC resistor voltage. Neither node
alone is the requested differential output. The gallery checks every nonground
node as well as the primary output. Expected values were calculated separately
from Ohm's law, KCL, impedance equations, and the finite-gain opamp equation; see
the [analytic reference](../docs/validation/analytic-reference.md).

`electrical.py` runs actual ngspice in a fresh analysis directory, rejects errors
even when ngspice returns exit code zero, parses named voltage vectors from ASCII
raw output, verifies the requested frequency, and compares complex differences.
The tolerance is `1e-9 V + 1e-6 × |expected|`. Missing vectors, truncated output,
NaN/Inf, timeout, absent executables, and mismatches fail the command. Each report
includes the canonical specification SHA-256 and simulator version.

## Scope and boundaries

These checks apply to the stated ideal models and requested DC/AC points. They
do not establish stability, transient behavior, component ratings, tolerance
analysis, wiring safety, or real-device performance. The opamp has gain `1e6` in
the gallery, infinite input impedance and zero output impedance; no supply rails,
saturation, bandwidth, slew rate, or output-current limit are modeled. Negative
feedback must also be checked from the actual pins. Algebraic DC solutions do not
prove physical feedback stability.

Diodes, BJT/MOSFETs, logic, switches and photo reconstruction use the freeform
workflow and its manual connection-table review. Their bundled examples are
render-tested, not ngspice-verified by this linear schema. Do not label an
unsupported circuit electrically verified merely because its PDF compiles.

Primary technical references: [CircuiTikZ manual](https://circuitikz.github.io/circuitikz/circuitikzmanualgit.pdf),
[ngspice documentation](https://ngspice.sourceforge.io/docs.html), and
[ngspice control language tutorial](https://ngspice.sourceforge.io/ngspice-control-language-tutorial.html).
