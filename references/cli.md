# Compiler and example CLI

Run commands from the repository root, or use absolute script paths.

## Commands

```bash
python scripts/example.py --list
python scripts/example.py --name divider --output-dir build/divider --compile --format svg --format png
python scripts/compile_circuit.py build/divider/divider.tex --format svg --format png
python scripts/compile_circuit.py assets/template-zh.tex --engine xelatex --output-dir build/chinese --format png
```

`example.py` refuses to overwrite existing TeX. Edit that copy and call
`compile_circuit.py` to rebuild it. Paths are resolved correctly from any working
directory; source-relative `\input` and images remain relative to the TeX file.
The source filename need not be a valid TeX job name.

| Option | Behavior |
|---|---|
| `--output-dir DIR` | Default: source directory; creates missing directories |
| `--format pdf/svg/png` | Repeat for desired exports; PDF is always retained; default PDF only |
| `--engine pdflatex/xelatex/lualatex` | Explicit engine; default `pdflatex` |
| `--timeout N` | Finite positive seconds per command; default 60 |
| `--passes N` | 1–3 LaTeX runs; default 2 |
| `--dpi N` | PNG resolution, 36–1200; default 180 |
| `--check` | Compile the bundled default template, including requested conversions |

Exit codes: **0** success, **1** build/dependency/I/O failure, **2** invalid CLI
syntax. Compilation/conversion logs are saved as `<name>.compile.log` (preflight
errors may occur before a log exists). `--check` uses temporary files and prints
failure diagnostics before cleanup. Requested export failures are fatal. SVG/PNG
requires a one-page PDF; multi-page input is rejected instead of silently losing
pages. PDF-only compilation can retain multiple pages.

Compilation uses a fresh temporary job, bounded commands, disabled shell escape,
and per-file atomic replacement after all requested conversions succeed. On a
compile/conversion failure, existing outputs are preserved and **may be stale**;
only the paths printed after a successful run represent the current build.
Successful builds also keep warnings in the log. Missing-glyph diagnostics are
fatal so unsupported labels are not silently omitted. Output publication is atomic
per file, not a multi-file transaction; an I/O failure during publication can leave
only some outputs updated. Use separate output directories for concurrent builds
of the same source basename.

The original import remains available: `compile_circuit(path)` returns `bool`.
For structured results, use `build(path, formats=("pdf", "svg"))`, which returns
`BuildResult(artifacts, log, warnings)` and raises `BuildError`. Default SVG export
is now opt-in to make dependencies and deliverables predictable.
