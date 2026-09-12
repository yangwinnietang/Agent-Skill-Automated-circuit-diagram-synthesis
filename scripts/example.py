#!/usr/bin/env python3
"""Copy a complete example to a user output directory, optionally compile it."""
import argparse
from pathlib import Path
import sys

try:
    from .compile_circuit import _print_message, compile_circuit
except ImportError:
    from compile_circuit import _print_message, compile_circuit


def main(argv=None):
    examples = Path(__file__).resolve().parents[1] / "assets" / "examples"
    names = sorted(path.stem for path in examples.glob("*.tex"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--name", choices=names, default="divider")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--format", choices=("pdf", "svg", "png"), action="append")
    args = parser.parse_args(argv)
    if args.list:
        _print_message("\n".join(names))
        return 0
    if args.output_dir is None:
        parser.error("Provide --output-dir (or use --list).")
    if args.format and not args.compile:
        parser.error("--format requires --compile.")
    target = args.output_dir.expanduser().resolve() / (args.name + ".tex")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects existing user edits.
        with target.open("x", encoding="utf-8") as output:
            output.write((examples / target.name).read_text(encoding="utf-8"))
    except OSError as exc:
        _print_message(f"Error: {exc}", file=sys.stderr)
        return 1
    _print_message(f"TeX: {target}")
    if args.compile:
        return 0 if compile_circuit(target, formats=args.format or ("pdf",)) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
