# Validation

## Reproduce

Fast checks (Python 3.9+, no third-party Python dependencies):

```bash
python -m unittest discover -s tests -p test_compile.py -v
python -m unittest discover -s tests -p test_resources.py -v
```

Full real-tool suite, including three engines and Chinese labels:

```bash
CIRCUIT_RUN_INTEGRATION=1 \
CIRCUIT_TEST_ENGINES=pdflatex,xelatex,lualatex \
CIRCUIT_TEST_CHINESE=1 \
python -m unittest discover -s tests -v
```

There are 43 fast test methods and 13 integration methods. One integration method
runs **17 complete documents per selected engine**, with PDF, SVG and PNG for each.
The corpus contains 12 component/topology examples, the default template, a known
image fixture, and 3 diagrams independently authored by agents using the skill.
Integration is opt-in locally; when enabled, missing required tools are failures.
Chinese and missing-glyph checks require their documented environment flags.
The GitHub workflow enables all of them; no rendering checks are skipped there.

## What is checked

| Layer | Observable behavior |
|---|---|
| Input and CLI | Bare, relative, absolute, spaced and Unicode paths; relative includes; missing inputs; invalid arguments; exit codes |
| Failure recovery | Real malformed TeX, missing tools, timed-out processes, failed converters, missing/invalid artifacts, missing glyphs; old outputs preserved |
| Output | PDF signature; parseable SVG with vector paths and no embedded raster; PNG signature/dimensions; single-page export contract |
| Source integrity | Source untouched, example copies never overwrite edits, isolated concurrent build jobs, atomic file replacement |
| Polarity | PDF text bounding boxes verify that the voltage source's rendered `+` is above `−`; independent of source-text assertions |
| Chinese | XeLaTeX compilation, all three exports, extracted Chinese label text, visual inspection |
| Resources | Working image PNG checksums/decompression, damaged original retained, resolvable skill resource links |
| Process controls | Shell escape disabled and process timeouts actually exercised; these do not constitute a security sandbox |

Unit tests inject tool failures; they do not substitute for integration tests. The
`pdf2svg` fallback is covered by a mocked contract test; the real conversion matrix
uses Poppler. Multi-page PDF-only output is allowed, while SVG/PNG rejects it.

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

## Execution record (2026-09-11)

Local verification uses Python 3.12, TeX Live 2023 engines and Poppler 24.02.0.
Both CircuiTikZ 1.6.6 and the separately obtained 1.8.6 are exercised. The supplied
container initially lacked usable format files, font maps, Chinese packages and
LuaLaTeX dependencies; these were provisioned in an isolated local TeX tree.
Normal installations should use their distribution package manager, not mix
current CTAN language packages into an older LaTeX kernel.

- Fast checks: 43 methods passed.
- Revised full local suite with XeLaTeX selected: **56 tests passed, no skips**,
  including all 17 documents, Chinese, missing glyphs, polarity and CLI checks.
- Initial corrected real suite: pdfLaTeX and XeLaTeX, all 12 examples plus template
  passed; the 49-method suite at that point passed with its optional Chinese test
  disabled. The expanded corpus and additional regressions are included in CI.
- CircuiTikZ 1.8.6: the expanded 17-document pdfLaTeX rendering corpus passed.
- Targeted three-engine rendered polarity check passed; real XeLaTeX missing-glyph
  rejection passed. Chinese template compiled to PDF/SVG/PNG and was visually read.
- Manual visual review covered all 12 example layouts, both text-generated
  diagrams, the reference image and the independently reconstructed image.

The initial CI run found a Windows-only test assertion issue: a temporary path in
8.3 short-name form was compared with its resolved long form. The assertion now
compares resolved paths. The next Windows run exposed locale-dependent decoding
of UTF-8 Markdown in the resource test; resource/log reads now select UTF-8
explicitly. Local extended runs also exposed an undetermined page
count being reported as a multi-page document; pdfinfo output is now parsed
separately and reports the exact failure category.

The full final CI run is the authoritative fresh-install and cross-platform
record; its status is available on the pull request. The workflow runs Python
3.9/3.12 fast checks on Linux/Windows and the complete three-engine rendering suite
on Ubuntu 24.04. Cross-platform rendering outside that Linux job is not claimed.

## Limits

Tests verify build behavior, known examples and a small set of independent agent
runs. They are not a statistical benchmark of arbitrary circuit photos or a proof
of electrical correctness. SVG/PNG appearance and terminal-table comparison remain
necessary. No SPICE simulation, hardware testing, PCB verification, or electrical
certification was performed. Font/package warnings remain visible in logs; the
expected disabled-shell-escape warning does not invalidate a drawing.
