# Verification and reproducibility

## Run the checks

Fast tests require only Python 3.9+ and the complete repository:

```bash
python -m unittest discover -s tests -v
```

On Linux the suite contains **126 test methods**: 103 run without external tools; 23 require
real rendering or simulation and are skipped unless their flags are enabled.
Windows additionally skips three POSIX-specific checks.
Enable all checks on a machine with the dependencies in the README:

```bash
CIRCUIT_RUN_INTEGRATION=1 \
CIRCUIT_RUN_SPICE=1 \
CIRCUIT_TEST_ENGINES=pdflatex,xelatex,lualatex \
CIRCUIT_TEST_CHINESE=1 \
python -m unittest discover -s tests -v
```

For PowerShell, set each flag with `$env:CIRCUIT_RUN_SPICE = '1'` (and the other
three variables) before running the same Python command. When a real-tool flag is
enabled, a missing dependency fails the check rather than quietly skipping it.

Rebuild the complete valued gallery:

```bash
python scripts/build_gallery.py --output-dir build/gallery
```

This produces 12 TeX sources, 12 PDFs, 12 SVGs, 12 PNGs, connection tables, 24 actual
SPICE analyses, and a JSON summary. Use `--overwrite` explicitly for an existing
generated gallery. To update the published artifacts, select `--output-dir
docs/gallery`, then inspect every changed PNG and update the visual review record.
The preview illustration is composed from the actual vector exports.

## Evidence for the twelve circuits

- [Gallery and downloads](docs/gallery/README.md)
- [Independent formulas, terminal maps and expected values](docs/validation/analytic-reference.md)
- [Machine-readable independent oracle](tests/oracles/electrical-ground-truth.json)
- [Numerical summary](docs/gallery/summary.json)
- [Individual visual inspections](docs/validation/visual-review.md)
- [SHA-256 identities of reviewed PNGs](docs/validation/visual-review.json)

The canonical gallery passes **24 DC/AC analyses and 81 voltage comparisons**.
Every nonground node is checked, as well as the explicitly defined output. The
maximum absolute error is **1.5687 × 10⁻¹¹ V**, compared with a tolerance of
`1e-9 V + 1e-6 × |expected|`. AC comparisons use complex voltage differences;
phase wrapping and undefined phase at zero are not used as pass/fail criteria.

Independent equations were established before examining generator or simulator
output. The DC reference uses Ohm's law and KCL; the filter reference uses complex
impedances; opamp values include finite gain A = 10⁶. A separate reviewer checked
all ordered terminals and component values against that reference. Each PNG was
opened and manually traced by the primary reviewer and one additional agent.

Visual review found two real problems: the first current-source style omitted its
arrow, and hollow measurement markers covered bridge junction dots. Both were
corrected, regenerated and inspected again. The final source has explicit symbol
styles and preserves solid branch dots underneath port labels.

Each circuit's simulation folder retains `.cir`, ASCII `.raw`, `.log`, and
`report.json` files. Reports include the simulator version, canonical spec hash,
expected and actual values, errors, and tolerances. They are actual execution
records, not hand-entered PASS labels. Generated sources and simulation netlists
are checked against the current specifications; reviewed image hashes are also
checked to catch stale published evidence.

## Test coverage

| Layer | Checks and concrete failures covered |
|---|---|
| Compilation (47 methods) | Real/bare/Unicode paths, source-relative includes, invalid options, engine/converter errors, empty or invalid artifacts, native TeX missing-glyph logs, timeout, no shell escape, narrow console encodings, relative PATH executables |
| Electrical engine (26 methods) | Strict fields/units, duplicated JSON keys, dangling/shorted/floating structures, opamp anchors, polarity, malformed/truncated/nonfinite raw data, absent vectors, error text with exit 0, stale raw output, version/provenance, tiny-frequency mismatch |
| Synthesis (19 methods) | Source-only and real exports, all 12 cases, literal label escaping, rendered source signs, namespace collisions, explicit overwrite, stale images/reports, failed-job evidence, symlink/directory conflicts |
| Independent electrical checks (8 methods) | All 12 terminal maps and counts, DC node values and signed branch currents, KCL, AC internal nodes, 30 parameter analyses, 5 incorrect-circuit analyses |
| General real rendering (13 methods) | 17-document corpus per selected engine; three formats, multipage contract, Chinese labels, missing glyphs, concurrent jobs, toolchain preflight, source polarity |
| Gallery publication (5 methods) | Full-spec preflight, existing metadata protection, symlink/type conflicts, invalid later input, failed preview/index/summary writes, no false PASS |
| Resources and published evidence (8 methods) | Decodable image fixture, preserved corrupt original, local links, all 12 export triplets, spec/netlist/report consistency, reviewed PNG hashes |

The independent parameter tests execute **30 additional analyses**, varying source
sign and amplitude, resistor decades, filter parts and frequency, current-source
sign, and opamp gain. Five deliberately incorrect but structurally valid circuits
must fail voltage comparisons: reversed voltage-source polarity, reversed
current-source arrow, wrong load, reversed RLC differential output, and wrong
opamp input polarity. These are expected numerical failures, not missing-tool failures.

The broader render corpus contains the original 12 component examples, the default
template, a known image fixture, and 3 independently authored forward-use diagrams.
One test renders all 17 with each selected engine in PDF, SVG and PNG. The actual
converter matrix uses Poppler; the alternate `pdf2svg` path has a mocked contract
test rather than a claimed real fallback run.

## Execution environment and CI

Local execution uses Python 3.12, TeX Live 2023 engines, CircuiTikZ 1.6.6, Poppler
24.02.0 and ngspice 42. Earlier rendering validation also exercised CircuiTikZ
1.8.6. The restricted development runtime needed scratch-local TeX format/font
files and ngspice temporary-file compatibility. Those environment repairs are
not repository dependencies; normal installations use the distribution packages.

The local three-engine main regression completed 120 methods with no skips; the six final gallery/publication checks added during review passed separately.

The GitHub workflow runs the fast suite on Linux and Windows with Python 3.9 and
3.12, then installs real dependencies on Ubuntu 24.04 and runs all flags, all three
engines and Chinese checks. See [current workflow runs](https://github.com/yangwinnietang/Agent-Skill-Automated-circuit-diagram-synthesis/actions/workflows/test.yml).
Cross-platform rendering outside that Linux job is not claimed.

## Independent skill use

Agents received only the skill, realistic requests and the necessary raw inputs;
they did not receive expected terminal tables or the test implementation.

| Request | Observed result and review |
|---|---|
| Text: ideal inverting amplifier (10 kΩ / 100 kΩ), and 5 V Wheatstone bridge, American resistors | Two editable diagrams rendered and visually reviewed. Correct feedback pin, open ports, bridge midpoints and specified symbol style. First pass exposed unbraced equals labels and a wrong source-polarity statement; both were corrected in templates/reference and retained in regression coverage. |
| Original repository `photo.png` | Agent identified Base64 text containing a corrupt PNG and declined to invent a full circuit from a partial decode. Exact original bytes retained in `tests/fixtures/original-photo.png.base64`. |
| New valid schematic image, with no access to its TeX or expected table | Agent recovered all 7 components, values, 4 nets, diode anode/cathode, source polarity and open Vout. Source, terminal table and output image were independently compared with ground truth. |

Raw successful outputs are retained in `tests/forward/`. The textual verification
record describes the first trial, including errors found before the skill was
corrected; it is not a claim that the original instructions were already correct.
The new `photo.png` is rendered from `tests/fixtures/reference-network.tex`, with
explicit ground truth in the adjacent JSON. It is a newly authored input fixture,
not a repair or guessed reconstruction of the corrupted original image.

## Limits

These checks establish correspondence and numerical agreement for the listed
circuits under their explicit ideal models. They do not prove arbitrary image
reconstruction accuracy, physical opamp stability, transient behavior, component
ratings, tolerance behavior, PCB connectivity or hardware safety. There has been
no physical hardware testing or design certification.

The opamp model has no rails, saturation, bandwidth, slew rate or current limit.
A DC solution is not a stability analysis. The freeform semiconductor and logic
examples are render-tested; they are not simulated by the restricted linear
schema. Geometric wire crossings and label overlap still require visual review.
Disabled TeX shell escape is not an isolation boundary for hostile TeX.

Publication is atomic per file, not across an entire directory. Old outputs can
remain after a failed job and must not be presented as a new success. Warnings and
failure evidence remain available for inspection.
