---
name: circuit-diagram-generator
description: Create or reconstruct electrical schematics from text, circuit photos, or existing LaTeX using CircuiTikZ. Deliver editable TeX and verified PDF, SVG, or PNG diagrams for reports, teaching, and publications. Includes optional ngspice checks for specified linear circuits. Use for schematics, not PCB layout or hardware certification.
---

# Circuit Diagram Generator

Generate the requested circuit with correct connectivity first, then refine its layout. The agent resolves topology, then authors either a structured linear-circuit specification or freeform TeX. Scripts render the result; optional ngspice checks compare ideal-model voltages with independent expectations. Compilation alone does not prove electrical correctness.

## 1. Resolve topology before drawing

- Identify components, values/units, named nets, terminal connections, source polarities, current reference directions, and open terminals. For branched circuits or images, make a compact connection table: `component | pin/terminal | net`. Treat geometric bends on a continuous wire as the same net.
- Preserve the requested circuit, including intentionally open or unusual connections. Do not add a ground, supply, load, component value, or return wire just to make the diagram look conventional. Clearly state any assumption that affects connectivity or polarity; ask when it cannot be resolved from the input.
- For images, inspect the actual image before transcribing it. Distinguish junction dots from wire crossings, open terminals, and compression artifacts. Preserve readable labels and symbol style. Record unreadable labels as unknown; request a crop or clarification for ambiguous connections. Do not describe an uncertain transcription as exact. See [image reconstruction](references/image-reconstruction.md).
- Use explicit terminal names for multi-pin devices: op-amp `+`, `-`, `out`, supply pins; BJT `B/C/E`; MOSFET `G/D/S/B` when shown. A device center is not a pin. Do not infer a real package pinout from the generic schematic symbol.

## 2. Choose a generation route

For circuits composed of R/C/L, independent V/I sources, and signal-only ideal opamps, use the [structured specification](references/structured-circuits.md) when numerical checks are useful. Start from an appropriate JSON in `assets/verified-circuits/`; change both the terminal model and independently derived expectations to match the request. Never copy simulator output into expected values just to pass. The same terminal list drives TeX and SPICE.

```bash
python <skill-dir>/scripts/synthesize.py /path/to/circuit.json \
  --output-dir /path/to/output --format svg --format png --verify
```

This requires ngspice for `--verify`, and refuses to overwrite prior artifacts unless `--overwrite` is explicit. Without `--verify`, no electrical simulation is claimed. The schema deliberately rejects unsupported components, undefined/shorted terminals, disconnected same-net points and structural floating networks. It does not detect arbitrary geometric crossings or model real device limits.

For arbitrary components, nonstandard notation, photos, or intentionally open/unusual circuits outside that schema, author freeform CircuiTikZ and check its terminal table manually. Do not force the circuit into a restricted model or silently replace semiconductor devices with linear parts.

## 3. Write editable CircuiTikZ

Resolve all bundled paths relative to this SKILL.md, not the user's current directory. Keep generated files in the task's output directory, outside the installed skill.

- Start with [assets/template.tex](assets/template.tex). Its loop is an example: replace it with the requested topology. Default to rectangular resistors when style is unspecified, but honor user or image choices. Use component-specific style options; `american voltages` alone does not select all American symbols. Do not claim the default meets every publication or electrical-symbol standard.
- For Chinese labels, start with [assets/template-zh.tex](assets/template-zh.tex) and use `--engine xelatex`. It requires `ctex` and Fandol fonts. Other Unicode text needs a font that actually contains its glyphs; changing engine alone is insufficient.
- Use named coordinates for repeated connection points and named device anchors for pins. Mark actual branch junctions explicitly. Avoid ambiguous four-way crossings; route unconnected wires apart or use an explicit wire jump. Never let a routing change alter the connection table.
- Put electrical quantities in math mode and units upright, e.g. `l={$R_1=10\,\mathrm{k}\Omega$}`. Wrap label values in braces to protect embedded equals signs or commas from PGF parsing. Escape literal TeX characters in user labels (`%`, `&`, `_`, `#`, braces); do not insert arbitrary label text as executable TeX.
- Source orientation, `invert`, voltage annotations and current arrows interact. Verify the rendered signs/arrows against the intended terminal table, especially after reversing or rotating a path. Consult [references/reference.md](references/reference.md) for syntax and component examples; use the linked official manual for unfamiliar symbols.
- Use `python <skill-dir>/scripts/example.py --list` to find complete, runnable examples (divider, bridge, RC/RLC, diode, transistor, op-amp, logic, crossings). Adapt them only when their topology fits.

## 4. Compile and inspect

Check the actual toolchain when it is unknown:

```bash
python <skill-dir>/scripts/compile_circuit.py --check
```

Compile with an explicit output directory and requested formats:

```bash
python <skill-dir>/scripts/compile_circuit.py /path/to/circuit.tex \
  --output-dir /path/to/output --format svg --format png
```

PDF is always produced. SVG/PNG require Poppler (`pdftocairo`, `pdfinfo`); SVG also supports `pdf2svg` plus `pdfinfo`. Default output is PDF only. Use `--engine xelatex` for the Chinese template, `--timeout` for a justified per-command limit, and `--dpi` for PNG resolution.

- On failure, read the reported `.compile.log`, fix the actual cause, and rerun. Stop after three failed repair attempts and report the blocker plus editable source; do not silently change connectivity or substitute a missing component. Missing dependencies may require installation appropriate to the environment; see [README.md](README.md).
- Only report output paths from a successful run. Older outputs are preserved on compilation/conversion failure and may be stale. Requested export failures return nonzero; never report a missing SVG as delivered. SVG/PNG export rejects multi-page PDFs rather than dropping pages.
- Open the rendered PNG or PDF with available image/PDF viewing tools. Check component identity/count, wire endpoints and junctions against the connection table; then polarity, arrows, labels, clipping, spacing, and crossings. Trace each branch rather than relying on visual similarity. A successful process exit checks rendering, not these properties.
- For numerical verification, first derive DC node values and, where relevant, complex AC outputs from circuit laws or an independent trusted calculation. Check the measurement polarity: a voltage across a floating resistor is differential. Compare all stated quantities, retain raw results, and report the model and tolerance. A finite-gain opamp differs slightly from the infinite-gain formula; omitted rails, saturation, dynamics and feedback stability are outside the bundled model. See [verification reference](docs/validation/analytic-reference.md).
- If rendering or viewing is unavailable, deliver TeX with the precise limitation and instructions to compile; do not claim visual verification. The compiler is not a sandbox for hostile TeX; inspect untrusted source and use an isolated environment when needed.

## 5. Deliver

Provide editable `.tex` and requested successful renderings. Briefly state assumptions, unresolved image details, and which checks actually ran. For complex reconstructions, include the connection table so the user can audit the topology. Distinguish structural checks, visual inspection, and numerical comparisons. Include assumptions and actual verification evidence when simulation ran; never turn an ideal-model pass into a hardware guarantee. PCB layout and design certification are outside scope.
