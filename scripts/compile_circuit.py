#!/usr/bin/env python3
"""Compile CircuiTikZ documents (Python 3.9+, standard library only).

This is a build tool, not a TeX security sandbox or an electrical-rule checker.
"""
import argparse
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


class BuildError(Exception):
    """An actionable input, dependency, compilation, or conversion failure."""


@dataclass
class BuildResult:
    artifacts: dict
    log: Path
    warnings: list


def _tool(name):
    executable = shutil.which(name)
    if not executable:
        raise BuildError(f"Required command '{name}' not found on PATH. See README.md dependencies.")
    return executable


def _run(command, cwd, log, timeout):
    """Bound each subprocess and retain output without buffering it in RAM."""
    env = os.environ.copy()
    env.update(openout_any="p", LC_ALL="C")
    log.write(("\n$ " + " ".join(map(str, command)) + "\n").encode())
    log.flush()
    try:
        with subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                              stdout=log, stderr=subprocess.STDOUT,
                              start_new_session=(os.name == "posix")) as process:
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
                raise BuildError(f"{Path(command[0]).name} timed out after {timeout:g}s.")
    except OSError as exc:
        raise BuildError(f"Could not run {Path(command[0]).name}: {exc}") from exc
    if code:
        raise BuildError(f"{Path(command[0]).name} failed (exit {code}).")


def _validate_artifact(path, kind):
    if not path.is_file() or path.stat().st_size == 0:
        raise BuildError(f"Tool reported success but produced no nonempty {kind.upper()} file.")
    with path.open("rb") as stream:
        header = stream.read(8)
    if kind == "pdf" and not header.startswith(b"%PDF-"):
        raise BuildError("Compiler output is not a PDF.")
    if kind == "png" and header != b"\x89PNG\r\n\x1a\n":
        raise BuildError("Converter output is not a PNG.")
    if kind == "svg":
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            raise BuildError("Converter produced malformed SVG XML.") from exc
        if root.tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
            raise BuildError("Converter output is not an SVG.")


def _publish(source, destination):
    """Replace a single output atomically, including across filesystem boundaries."""
    fd, name = tempfile.mkstemp(prefix=".publish-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as stream:
            shutil.copyfileobj(stream, output)
        os.replace(name, destination)
    finally:
        Path(name).unlink(missing_ok=True)


def build(tex_file, *, output_dir=None, engine="pdflatex", formats=("pdf",),
          timeout=60, passes=2, dpi=180):
    """Build PDF and requested conversions; raise BuildError on failure.

    Relative includes resolve from the source directory. Previous deliverables are
    preserved on compile/conversion failure; only result paths are current.
    Each command has its own timeout. SVG/PNG accept one-page documents only.
    """
    if engine not in ("pdflatex", "xelatex", "lualatex"):
        raise BuildError("Engine must be pdflatex, xelatex, or lualatex.")
    if isinstance(formats, str):
        formats = (formats,)
    formats = tuple(dict.fromkeys(("pdf", *formats)))
    if any(kind not in ("pdf", "svg", "png") for kind in formats):
        raise BuildError("Formats must be pdf, svg, or png.")
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise BuildError("Timeout must be finite and positive.")
    if type(passes) is not int or not 1 <= passes <= 3:
        raise BuildError("Passes must be an integer from 1 to 3.")
    if type(dpi) is not int or not 36 <= dpi <= 1200:
        raise BuildError("DPI must be an integer from 36 to 1200.")
    source = Path(tex_file).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".tex":
        raise BuildError(f"Expected an existing .tex file: {source}")
    compiler = _tool(engine)
    converters = {}
    if "svg" in formats:
        converters["svg"] = shutil.which("pdftocairo") or shutil.which("pdf2svg")
        if not converters["svg"]:
            raise BuildError("SVG requires pdftocairo (Poppler) or pdf2svg.")
    if "png" in formats:
        converters["png"] = _tool("pdftocairo")
    info = _tool("pdfinfo") if converters else None
    destination = Path(output_dir).expanduser().resolve() if output_dir else source.parent
    log_path = destination / (source.stem + ".compile.log")
    try:
        destination.mkdir(parents=True, exist_ok=True)
        # Fixed job name avoids interpreting source filenames as TeX code.
        with tempfile.TemporaryDirectory(prefix="circuit-build-") as temp:
            work = Path(temp)
            staged = work / "circuit.tex"
            shutil.copyfile(source, staged)
            raw_log = work / "build.log"
            try:
                with raw_log.open("wb") as log:
                    command = [compiler, "-no-shell-escape", "-interaction=nonstopmode",
                               "-halt-on-error", "-file-line-error", "-jobname=circuit",
                               f"-output-directory={work}", str(staged)]
                    for _ in range(passes):
                        _run(command, source.parent, log, timeout)
                    pdf = work / "circuit.pdf"
                    _validate_artifact(pdf, "pdf")
                    log.flush()
                    log_text = raw_log.read_text(encoding="utf-8", errors="replace")
                    warnings = [line.strip() for line in log_text.splitlines()
                                if "Warning:" in line or "Overfull" in line or "Underfull" in line]
                    if "Missing character:" in log_text:
                        raise BuildError("Missing glyphs in output; choose a font/engine that covers the labels.")
                    if converters:
                        # Parse pdfinfo's own output, not a mixed multi-command log.
                        info_path = work / "pdfinfo.log"
                        try:
                            with info_path.open("wb") as info_log:
                                _run([info, str(pdf)], source.parent, info_log, timeout)
                        finally:
                            if info_path.exists():
                                log.write(info_path.read_bytes())
                                log.flush()
                        pages = re.findall(r"^Pages:\s+(\d+)\s*$", info_path.read_text(encoding="utf-8", errors="replace"), re.M)
                        if len(pages) != 1:
                            raise BuildError("Could not determine PDF page count from pdfinfo output.")
                        if int(pages[0]) != 1:
                            raise BuildError(f"SVG/PNG export requires exactly one PDF page; received {pages[0]}. Split the document first.")
                    generated = {"pdf": pdf}
                    for kind, executable in converters.items():
                        artifact = work / f"circuit.{kind}"
                        if kind == "png":
                            command = [executable, "-png", "-singlefile", "-r", str(dpi), str(pdf), str(work / "circuit")]
                        elif Path(executable).stem == "pdf2svg":
                            command = [executable, str(pdf), str(artifact), "1"]
                        else:
                            command = [executable, "-svg", str(pdf), str(artifact)]
                        _run(command, source.parent, log, timeout)
                        _validate_artifact(artifact, kind)
                        generated[kind] = artifact
                artifacts = {kind: destination / f"{source.stem}.{kind}" for kind in generated}
                for kind, artifact in generated.items():
                    _publish(artifact, artifacts[kind])
            finally:
                if raw_log.exists():
                    _publish(raw_log, log_path)
            return BuildResult(artifacts, log_path, list(dict.fromkeys(warnings)))
    except BuildError as exc:
        raise BuildError(f"{exc} Build log: {log_path}") from exc
    except OSError as exc:
        raise BuildError(f"File operation failed: {exc}") from exc


def compile_circuit(tex_file, **options):
    """Backward-compatible Boolean helper; default output is PDF only."""
    try:
        result = build(tex_file, **options)
    except BuildError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return False
    for kind, path in result.artifacts.items():
        print(f"{kind.upper()}: {path}")
    print(f"Log: {result.log}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tex_file", nargs="?")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--engine", choices=("pdflatex", "xelatex", "lualatex"), default="pdflatex")
    parser.add_argument("--format", dest="formats", choices=("pdf", "svg", "png"), action="append",
                        help="Repeat for multiple outputs; PDF is always retained (default: PDF only).")
    parser.add_argument("--timeout", type=float, default=60, help="Seconds per command (default: 60).")
    parser.add_argument("--passes", type=int, default=2, help="LaTeX passes, 1–3 (default: 2).")
    parser.add_argument("--dpi", type=int, default=180, help="PNG resolution, 36–1200 (default: 180).")
    parser.add_argument("--check", action="store_true", help="Actually compile the bundled template to check the toolchain.")
    args = parser.parse_args(argv)
    if args.check and args.tex_file:
        parser.error("Use --check without an input file.")
    if not args.check and not args.tex_file:
        parser.error("Provide a .tex file or use --check.")
    options = dict(engine=args.engine, formats=args.formats or ("pdf",), timeout=args.timeout,
                   passes=args.passes, dpi=args.dpi)
    if args.check:
        template = Path(__file__).resolve().parents[1] / "assets" / "template.tex"
        with tempfile.TemporaryDirectory(prefix="circuit-check-") as temp:
            try:
                result = build(template, output_dir=temp, **options)
            except BuildError as exc:
                print(f"Toolchain check failed: {exc}", file=sys.stderr)
                for log in Path(temp).glob("*.compile.log"):
                    print(log.read_text(encoding="utf-8", errors="replace")[-6000:], file=sys.stderr)
                return 1
            print(f"Toolchain check passed: {args.engine}; {', '.join(result.artifacts)}.")
            for warning in result.warnings:
                print(f"Warning: {warning}", file=sys.stderr)
        return 0
    return 0 if compile_circuit(args.tex_file, output_dir=args.output_dir, **options) else 1


if __name__ == "__main__":
    sys.exit(main())
