#!/usr/bin/env python3
"""Rebuild every valued example, its three exports, and actual SPICE evidence."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from compile_circuit import BuildError, _print_message
from electrical import SimulationError, SpecError, load_spec, validate_spec
from synthesize import synthesize
from gallery_art import overview

ROOT = Path(__file__).resolve().parents[1]


def value_text(value):
    if isinstance(value, list):
        return f"{value[0]:.10g} {value[1]:+.10g}j"
    return f"{value:.10g}"


def relative_link(path, folder):
    return Path(os.path.relpath(path, folder)).as_posix()


def case_readme(spec, report, folder):
    ident = spec["id"]
    spec_link = relative_link(ROOT / f"assets/verified-circuits/{ident}.json", folder)
    analytic_link = relative_link(ROOT / "docs/validation/analytic-reference.md", folder)
    lines = [f"# {spec['title']}", "", f"![{spec['title']}]({ident}.svg)", "",
             f"[PDF]({ident}.pdf) · [PNG]({ident}.png) · [Editable TeX]({ident}.tex) · "
             f"[Connections]({ident}.connections.md) · "
             f"[JSON specification]({spec_link}) · "
             f"[Simulation report]({ident}.simulation/report.json)", "",
             "Generated from one terminal model shared by the drawing and SPICE exporter. "
             f"Expected values come from the [independent analytic reference]({analytic_link}). "
             "Voltage measurements use V(positive, negative); AC values are complex volts.", "",
             "| Analysis | Measurement | Expected (V) | ngspice (V) | Absolute error (V) | Result |",
             "|---|---|---:|---:|---:|---|"]
    for run in report["runs"]:
        analysis = "DC" if run["analysis"] == "dc" else f"AC {run['frequency_hz']:.9g} Hz"
        for name, m in run["measurements"].items():
            lines.append(f"| {analysis} | {name} | {value_text(m['expected'])} | "
                         f"{value_text(m['actual'])} | {m['absolute_error_v']:.3g} | "
                         + ("PASS" if m["passed"] else "FAIL") + " |")
    lines.extend(["", "All node voltages are checked. The `output` measurement can be differential; "
                  "for the RLC example it is the voltage across R, not a node-to-ground voltage.", ""])
    if spec.get("notes"):
        lines.extend(["Model assumptions:", ""] + ["- " + note for note in spec["notes"]] + [""])
    lines.extend(["Raw simulator output, each netlist, and process logs are retained beside "
                  "the JSON report. Rendering and these ideal-model comparisons do not certify "
                  "component ratings, PCB connectivity, or physical circuit performance.", ""])
    return "\n".join(lines)


def gallery_specs():
    """Validate every input before any case ID is used as an output path."""
    paths = sorted((ROOT / "assets/verified-circuits").glob("*.json"))
    if not paths:
        raise BuildError("No verified-circuit specs found")
    specs = []
    identifiers = set()
    for path in paths:
        spec = load_spec(path)
        validate_spec(spec)
        identifier = spec["id"].casefold()
        if identifier in identifiers:
            raise BuildError(f"Duplicate gallery case ID: {spec['id']}")
        identifiers.add(identifier)
        specs.append(spec)
    return specs


def check_metadata_destinations(target, specs, overwrite):
    """Protect gallery metadata independently of each case's generated files."""
    if target.exists() and not target.is_dir():
        raise BuildError(f"Expected an output directory: {target}")
    metadata = [target / name for name in ("summary.json", "README.md", "overview.svg")]
    for spec in specs:
        folder = target / spec["id"]
        if folder.is_symlink():
            raise BuildError(f"Refusing a symlink case directory: {folder}")
        if folder.exists() and not folder.is_dir():
            raise BuildError(f"Expected a case directory: {folder}")
        metadata.append(folder / "README.md")
    for path in metadata:
        if path.is_symlink():
            raise BuildError(f"Refusing a symlink metadata output: {path}")
        if path.exists():
            if not path.is_file():
                raise BuildError(f"Expected a metadata file: {path}")
            if not overwrite:
                raise BuildError(f"Refusing to overwrite {path}; choose another directory or use --overwrite.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/gallery")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--engine", choices=("pdflatex", "xelatex", "lualatex"), default="pdflatex")
    args = parser.parse_args(argv)
    try:
        specs = gallery_specs()
        target = args.output_dir.expanduser().resolve()
        check_metadata_destinations(target, specs, args.overwrite)
    except (BuildError, SpecError, OSError, ValueError) as exc:
        _print_message(f"Error: {exc}", file=sys.stderr)
        return 1
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "engine": args.engine,
               "status": "running", "case_count": len(specs), "analysis_count": 0,
               "measurement_count": 0, "maximum_absolute_error_v": 0, "cases": []}
    summary_path = target / "summary.json"
    index = ["# Verified circuit gallery", "", "Twelve valued circuits: editable source, "
             "three export formats, explicit terminal maps, and reproducible ideal-model comparisons.", "",
             f"[Verification method]({relative_link(ROOT / 'docs/validation/analytic-reference.md', target)}) · "
             f"[Visual inspection record]({relative_link(ROOT / 'docs/validation/visual-review.md', target)}) · [Machine summary](summary.json)", "",
             "| Circuit | DC output (V) | Analyses | Detail and downloads |",
             "|---|---:|---:|---|"]
    try:
        target.mkdir(parents=True, exist_ok=True)
        # Invalidate a previous global PASS before starting a partial rebuild.
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        for spec in specs:
            ident = spec["id"]
            folder = target / ident
            synthesize(spec, folder, formats=("pdf", "svg", "png"), verify=True,
                       overwrite=args.overwrite, engine=args.engine)
            report = json.loads((folder / f"{ident}.simulation/report.json").read_text(encoding="utf-8"))
            (folder / "README.md").write_text(case_readme(spec, report, folder), encoding="utf-8")
            measurements = [m for run in report["runs"] for m in run["measurements"].values()]
            error = max(m["absolute_error_v"] for m in measurements)
            summary["analysis_count"] += len(report["runs"])
            summary["measurement_count"] += len(measurements)
            summary["maximum_absolute_error_v"] = max(summary["maximum_absolute_error_v"], error)
            summary["cases"].append({"id": ident, "status": report["status"],
                                     "spec_sha256": report["spec_sha256"],
                                     "analyses": len(report["runs"]), "measurements": len(measurements),
                                     "maximum_absolute_error_v": error,
                                     "report": f"{ident}/{ident}.simulation/report.json"})
            output = spec["expected"]["dc"].get("output")
            dc = "n/a" if output is None else value_text(output)
            index.append(f"| {spec['title']} | {dc} | {len(report['runs'])} | [{ident}]({ident}/README.md) |")
            _print_message(f"PASS {ident}: PDF/SVG/PNG; {len(report['runs'])} analyses; max error {error:.3g} V")
        overview(target)
        index.extend(["", "Regenerate with `python scripts/build_gallery.py --output-dir build/gallery`. "
                      "Use `--overwrite` only to replace a previous generated gallery.", ""])
        (target / "README.md").write_text("\n".join(index), encoding="utf-8")
        summary["status"] = "pass"
    except (BuildError, SimulationError, SpecError, OSError, ValueError, KeyError, ET.ParseError) as exc:
        summary["status"] = "fail"
        summary["error"] = str(exc)
        _print_message(f"Error: {exc}", file=sys.stderr)
    finally:
        try:
            summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        except OSError as exc:
            summary["status"] = "fail"
            _print_message(f"Error saving gallery summary: {exc}", file=sys.stderr)
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
