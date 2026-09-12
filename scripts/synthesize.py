#!/usr/bin/env python3
"""Render a validated linear-circuit JSON spec to editable TeX and optional images.

The same ordered terminals feed the drawing and SPICE exporter. This deliberately
small, deterministic renderer does not infer a circuit from prose or a photo;
the agent resolves that input before authoring a spec or freeform CircuiTikZ.
"""
import argparse
import math
from pathlib import Path
import re
import shutil
import sys
import tempfile

try:
    from .compile_circuit import BuildError, _print_message, _publish, build
    from .electrical import SimulationError, load_spec, simulate, spice_netlist, validate_spec
except ImportError:
    from compile_circuit import BuildError, _print_message, _publish, build
    from electrical import SimulationError, load_spec, simulate, spice_netlist, validate_spec


def tex_escape(value):
    """Treat external labels as text, never as executable TeX."""
    replacements = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
                    "$": r"\$", "&": r"\&", "#": r"\#", "%": r"\%",
                    "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(c, c) for c in value)


def reference_label(ref):
    if len(ref) == 1:
        return ref
    suffix = tex_escape(ref[1:])
    return ref[0] + r"_{\mathrm{" + suffix + "}}"


def quantity(value, kind):
    """Engineering units for a numeric SI value (SPICE always receives SI)."""
    unit = {"R": r"\Omega", "C": r"\mathrm{F}", "L": r"\mathrm{H}",
            "V": r"\mathrm{V}", "I": r"\mathrm{A}"}[kind]
    prefixes = [(1e12, "T"), (1e9, "G"), (1e6, "M"), (1e3, "k"),
                (1, ""), (1e-3, "m"), (1e-6, r"\mu"), (1e-9, "n"), (1e-12, "p")]
    factor, prefix = 1, ""
    if value:
        factor, prefix = next(((f, p) for f, p in prefixes if abs(value) >= f), (1, ""))
    number = format(value / factor, ".15g")
    if "e" in number:
        mantissa, exponent = number.split("e")
        number = mantissa + r"\times 10^{" + str(int(exponent)) + "}"
    prefix = (r"\mathrm{" + prefix + "}") if prefix and prefix != r"\mu" else prefix
    return number + r"\," + prefix + unit


def render_tex(spec, *, chinese=False):
    """Return a complete standalone document after structural validation."""
    validate_spec(spec)
    packages = (r"\usepackage[UTF8,fontset=fandol]{ctex}" if chinese else
                "\\usepackage[T1]{fontenc}\n\\usepackage{lmodern}")
    lines = [r"\documentclass[border=12pt]{standalone}", packages,
             r"\usepackage{amsmath}",
             r"\usepackage[europeanresistors,americanvoltages,americancurrents,americaninductors]{circuitikz}",
             r"\definecolor{circuitink}{HTML}{20334A}", r"\begin{document}",
             "% Generated from validated JSON; edit the JSON to keep SPICE in sync.",
             "% V pins: [positive, negative]; I pins: [arrow from, arrow to].",
             r"\begin{circuitikz}[color=circuitink,thick,font=\small]"]
    devices = {c["ref"].casefold(): c["ref"] for c in spec["components"] if c["kind"] == "opamp"}
    for component in spec["components"]:
        if component["kind"] == "opamp":
            x, y = component["at"]
            lines.append(r"\node[op amp] (D" + component["ref"] + f") at ({x:.17g},{y:.17g}) "
                         + "{$" + reference_label(component["ref"]) + "$};")
    for point, node in spec["nodes"].items():
        if "at" in node:
            x, y = node["at"]
            position = f"({x:.17g},{y:.17g})"
        else:
            ref, pin = node["anchor"].split(".")
            pin = {"plus": "+", "minus": "-", "out": "out"}[pin]
            position = "(D" + devices[ref.casefold()] + "." + pin + ")"
        lines.append(r"\coordinate (P" + point + ") at " + position + ";")
    for component in spec["components"]:
        kind = component["kind"]
        if kind == "opamp":
            continue
        start, end = component["pins"]
        symbol = kind
        if kind == "V":
            start, end = end, start
            symbol = "V,invert"
        label = "$" + reference_label(component["ref"]) + r"$\\$" + quantity(component["value"], kind) + "$"
        if "ac" in component:
            label += r"\ DC\\$" + quantity(component["ac"], kind) + r"$\ AC"
        side = "l_" if component.get("label_side") == "below" else "l^"
        lines.append(r"\draw (P" + start + ") to[" + symbol + "," + side
                     + r"={\shortstack{" + label + "}}] (P" + end + ");")
    for a, b in spec["wires"]:
        route = "-|" if "anchor" in spec["nodes"][a] or "anchor" in spec["nodes"][b] else "--"
        lines.append(r"\draw (P" + a + ") " + route + " (P" + b + ");")
    for point in spec["grounds"]:
        lines.append(r"\draw (P" + point + ") node[ground] {};")
    for point in spec["junctions"]:
        lines.append(r"\node[circ] at (P" + point + ") {};")
    for port in spec["ports"]:
        marker = "" if port["point"] in spec["junctions"] else " node[ocirc] {}"
        lines.append(r"\draw (P" + port["point"] + ")" + marker + " node[above right] {"
                     + tex_escape(port["label"]) + "};")
    lines.extend([r"\end{circuitikz}", r"\end{document}", ""])
    return "\n".join(lines)


def connection_table(spec):
    """A human-auditable net table independent of point placement."""
    validate_spec(spec)
    lines = ["# " + spec["title"], "", "| Device | Model / SI value | Ordered terminals |",
             "|---|---|---|"]
    for c in spec["components"]:
        nets = [spec["nodes"][p]["net"] for p in c["pins"]]
        roles = ["+", "-", "out"] if c["kind"] == "opamp" else (
            ["+", "-"] if c["kind"] == "V" else ["from", "to"] if c["kind"] == "I" else ["1", "2"])
        model = "VCVS, A=" + str(c["gain"]) if c["kind"] == "opamp" else str(c["value"])
        if "ac" in c:
            model += "; AC=" + str(c["ac"])
        pins = ", ".join(f"{role}: `{net}`" for role, net in zip(roles, nets))
        lines.append(f"| {c['ref']} | {model} | {pins} |")
    lines.extend(["", "Current is positive from the first to the second source terminal. "
                  "Voltage is positive at the first voltage-source terminal. "
                  "An opamp is a signal-only VCVS referenced to net `0`.", "", "Measurements:", ""])
    for m in spec["analysis"]["measurements"]:
        lines.append(f"- `{m['name']}` = V(`{m['positive']}`, `{m['negative']}`).")
    if spec.get("notes"):
        lines.extend(["", "Model assumptions:", ""] + ["- " + n for n in spec["notes"]])
    return "\n".join(lines) + "\n"


def _existing_outputs(target, case_id):
    """Identify this case's generated files without claiming unrelated files."""
    candidates = [target / (case_id + suffix) for suffix in
                  (".tex", ".cir", ".connections.md", ".pdf", ".svg", ".png", ".compile.log")]
    simulation = target / (case_id + ".simulation")
    if simulation.is_symlink():
        raise BuildError(f"Refusing a symlink simulation directory: {simulation}")
    if simulation.exists():
        if not simulation.is_dir():
            raise BuildError(f"Expected a simulation directory: {simulation}")
        candidates.extend(path for path in simulation.iterdir()
                          if path.name == "report.json" or
                          re.fullmatch(r"(?:dc|ac_[0-9]+)\.(?:cir|raw|log)", path.name))
    existing = set()
    for path in candidates:
        if path.is_symlink():
            raise BuildError(f"Refusing a symlink output: {path}")
        if path.exists():
            if not path.is_file():
                raise BuildError(f"Expected a file output: {path}")
            existing.add(path)
    return existing


def synthesize(spec, output_dir, *, formats=(), verify=False, overwrite=False,
               engine="pdflatex", timeout=60, chinese=False):
    """Stage the entire job before publishing; refuse to replace source by default.

    Compilation or simulation failure preserves old deliverables. Publication
    is atomic per file, not across the whole directory. Successful overwrites
    remove this case's stale generated images and simulation reports.
    """
    validate_spec(spec)
    if isinstance(formats, str):
        formats = (formats,)
    formats = tuple(dict.fromkeys(formats))
    if any(kind not in ("pdf", "svg", "png") for kind in formats):
        raise BuildError("Formats must be pdf, svg, or png.")
    if engine not in ("pdflatex", "xelatex", "lualatex"):
        raise BuildError("Engine must be pdflatex, xelatex, or lualatex.")
    try:
        valid_timeout = type(timeout) in (int, float) and math.isfinite(timeout) and timeout > 0
    except OverflowError:
        valid_timeout = False
    if not valid_timeout:
        raise BuildError("Timeout must be finite and positive.")
    target = Path(output_dir).expanduser().resolve()
    source = target / (spec["id"] + ".tex")
    if target.exists() and not target.is_dir():
        raise BuildError(f"Expected an output directory: {target}")
    existing = _existing_outputs(target, spec["id"])
    if existing and not overwrite:
        raise BuildError(f"Refusing to overwrite {sorted(existing)[0]}; choose another directory or use --overwrite.")
    if chinese and engine != "xelatex":
        raise BuildError("Chinese labels require --engine xelatex with --chinese.")
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".synthesis-", dir=target.parent) as temporary:
        staged = Path(temporary)
        tex = staged / source.name
        tex.write_text(render_tex(spec, chinese=chinese), encoding="utf-8")
        (staged / (spec["id"] + ".connections.md")).write_text(connection_table(spec), encoding="utf-8")
        analysis = "dc" if spec["analysis"]["dc"] else spec["analysis"]["ac_hz"][0]
        (staged / (spec["id"] + ".cir")).write_text(spice_netlist(spec, analysis), encoding="utf-8")
        try:
            if formats:
                build(tex, output_dir=staged, engine=engine, formats=formats, timeout=timeout)
            if verify:
                simulate(spec, staged / (spec["id"] + ".simulation"), timeout=timeout)
        except (BuildError, SimulationError) as exc:
            # Preserve failure evidence without replacing any previous success.
            diagnostic = Path(tempfile.mkdtemp(prefix="failed-", dir=target))
            shutil.copytree(staged, diagnostic, dirs_exist_ok=True)
            raise BuildError(f"{exc}\nFailure evidence: {diagnostic}") from exc
        # Compilation can take time; protect files created or edited meanwhile.
        current = _existing_outputs(target, spec["id"])
        if current and not overwrite:
            raise BuildError(f"Refusing to overwrite {sorted(current)[0]}; output appeared while the job was running.")
        published = []
        for file in sorted(staged.rglob("*")):
            if file.is_file():
                destination = target / file.relative_to(staged)
                destination.parent.mkdir(parents=True, exist_ok=True)
                _publish(file, destination)
                published.append(destination)
        for stale in sorted(existing - set(published)):
            stale.unlink()
        simulation = target / (spec["id"] + ".simulation")
        if simulation.is_dir() and not any(simulation.iterdir()):
            simulation.rmdir()
    return published


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--format", action="append", choices=("pdf", "svg", "png"), default=[])
    parser.add_argument("--verify", action="store_true", help="Run ngspice and compare independent expected values")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly replace generated source and requested artifacts")
    parser.add_argument("--engine", choices=("pdflatex", "xelatex", "lualatex"), default="pdflatex")
    parser.add_argument("--chinese", action="store_true", help="Use the ctex/Fandol preamble; requires XeLaTeX")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(argv)
    try:
        spec = load_spec(args.spec)
        outputs = synthesize(spec, args.output_dir, formats=args.format, verify=args.verify,
                             overwrite=args.overwrite, engine=args.engine, timeout=args.timeout,
                             chinese=args.chinese)
    except (OSError, ValueError, BuildError, SimulationError) as exc:
        _print_message(f"Error: {exc}", file=sys.stderr)
        return 1
    for output in outputs:
        _print_message(str(output))
    if not args.verify:
        _print_message("Source generated; electrical simulation was not requested.")
    if not args.format:
        _print_message("No images requested. Use --format svg or --format png to compile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
