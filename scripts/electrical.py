#!/usr/bin/env python3
"""Validate a drawn circuit and check independent expectations with ngspice.

This schema models linear ideal components. In particular, an opamp is a
signal-only voltage-controlled voltage source, with no supply rails, bandwidth,
output limits, or other hardware behavior. Connectivity checks are deliberately
limited structural checks, not a general electrical rule checker.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


# ngspice ASCII output uses 15 digits; the independent linear-case oracle and
# real simulator agree well inside these tolerances, including near-zero nulls.
ABS_TOL_V = 1e-9
REL_TOL = 1e-6
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
NET_IDENTIFIER = re.compile(r"(?:0|[A-Za-z_][A-Za-z0-9_]*)\Z")
CASE_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")


class SpecError(ValueError):
    """An invalid or electrically inconsistent circuit specification."""


class SimulationError(RuntimeError):
    """A simulator or comparison failure; a saved report may be attached."""

    def __init__(self, message: str, *, report=None, report_path=None):
        super().__init__(message)
        self.report = report
        self.report_path = report_path


def _record(value, where, required, optional=()):
    if not isinstance(value, dict):
        raise SpecError(f"{where}: expected an object")
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing:
        raise SpecError(f"{where}: missing fields {', '.join(sorted(missing))}")
    if extra:
        raise SpecError(f"{where}: unknown fields {', '.join(sorted(map(str, extra)))}")


def _list(value, where):
    if not isinstance(value, list):
        raise SpecError(f"{where}: expected an array")
    return value


def _number(value, where, positive=False):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (positive and value <= 0):
        adjective = "finite positive" if positive else "finite"
        raise SpecError(f"{where}: expected a {adjective} number, got {value!r}")
    return float(value)


def _identifier(value, where, pattern=IDENTIFIER):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise SpecError(f"{where}: invalid identifier {value!r}")
    return value


def _text(value, where):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise SpecError(f"{where}: expected a nonempty single-line string")


def _coordinate(value, where):
    if not isinstance(value, list) or len(value) != 2:
        raise SpecError(f"{where}: expected [x, y]")
    return tuple(_number(v, f"{where}[{i}]") for i, v in enumerate(value))


class _UnionFind:
    def __init__(self, items):
        self.parent = {x: x for x in items}

    def find(self, item):
        while item != self.parent[item]:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def validate_spec(spec: dict) -> None:
    """Raise SpecError for malformed input or a provable structural fault.

    Same-net points must be joined by drawn wires; separate explicit ground
    symbols join net 0. A port terminates a drawn wire but creates no connection.
    The floating-network check uses component branches, with opamp outputs
    referenced to ground and opamp control inputs treated as open circuits.
    It does not prove a nonsingular operating point or real-world suitability.
    """
    _record(spec, "circuit", ("id", "title", "nodes", "components", "wires", "grounds",
                              "junctions", "ports", "analysis", "expected"),
            ("notes", "category"))
    _identifier(spec["id"], "id", CASE_IDENTIFIER)
    _text(spec["title"], "title")
    if "category" in spec:
        _text(spec["category"], "category")
    for i, note in enumerate(_list(spec.get("notes", []), "notes")):
        _text(note, f"notes[{i}]")
    nodes = spec["nodes"]
    if not isinstance(nodes, dict) or not nodes:
        raise SpecError("nodes: expected a nonempty object of drawing points")
    net_spellings = {}
    net_points = defaultdict(list)
    coordinates = {}
    anchors = {}
    for point, node in nodes.items():
        _identifier(point, "point ID")
        _record(node, f"nodes.{point}", ("net",), ("at", "anchor"))
        if ("at" in node) == ("anchor" in node):
            raise SpecError(f"nodes.{point}: provide exactly one of at or anchor")
        net = _identifier(node["net"], f"nodes.{point}.net", NET_IDENTIFIER)
        previous = net_spellings.setdefault(net.casefold(), net)
        if previous != net:
            raise SpecError(f"nodes.{point}.net: {net!r} and {previous!r} collide in SPICE; use one spelling")
        net_points[net].append(point)
        if "at" in node:
            coordinate = _coordinate(node["at"], f"nodes.{point}.at")
            if coordinate in coordinates:
                raise SpecError(f"nodes.{point}.at: coincides with {coordinates[coordinate]}; reuse one point ID")
            coordinates[coordinate] = point
        else:
            anchor = node["anchor"]
            if not isinstance(anchor, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*\.(plus|minus|out)", anchor):
                raise SpecError(f"nodes.{point}.anchor: expected an opamp anchor such as U1.plus")
            if anchor.casefold() in anchors:
                raise SpecError(f"nodes.{point}.anchor: duplicate anchor {anchor}")
            anchors[anchor.casefold()] = point

    def point_id(value, where):
        if not isinstance(value, str) or value not in nodes:
            raise SpecError(f"{where}: undefined point {value!r}")
        return value

    components = _list(spec["components"], "components")
    if not components:
        raise SpecError("components: provide at least one component")
    refs = {}
    degree = Counter()
    branches = _UnionFind(net_points)
    for i, component in enumerate(components):
        where = f"components[{i}]"
        if not isinstance(component, dict):
            raise SpecError(f"{where}: expected an object")
        kind = component.get("kind")
        if not isinstance(kind, str) or kind not in ("R", "C", "L", "V", "I", "opamp"):
            raise SpecError(f"{where}.kind: unsupported component kind {kind!r}")
        _record(component, where, ("ref", "kind", "pins", "gain", "at") if kind == "opamp"
                else ("ref", "kind", "pins", "value"),
                ("label_side",) if kind not in ("V", "I") else ("label_side", "ac"))
        ref = _identifier(component["ref"], f"{where}.ref")
        prefix = "U" if kind == "opamp" else kind
        if not ref.upper().startswith(prefix):
            raise SpecError(f"{where}.ref: {kind} reference must start with {prefix}")
        if ref.casefold() in refs:
            raise SpecError(f"{where}.ref: duplicate reference {ref!r} (case-insensitive)")
        refs[ref.casefold()] = component
        if "label_side" in component and component["label_side"] not in ("above", "below"):
            raise SpecError(f"{where}.label_side: expected above or below")
        pins = _list(component["pins"], f"{where}.pins")
        if len(pins) != (3 if kind == "opamp" else 2):
            raise SpecError(f"{where}.pins: {kind} needs {3 if kind == 'opamp' else 2} ordered pins")
        for j, point in enumerate(pins):
            point_id(point, f"{where}.pins[{j}]")
            degree[point] += 1
        pin_nets = [nodes[p]["net"] for p in pins]
        # Shorting an opamp input to its output is valid unity-gain feedback.
        # Shorting its two inputs is an unintended zero differential input.
        if kind != "opamp" and pin_nets[0] == pin_nets[1]:
            raise SpecError(f"{where} ({ref}): shorted component terminals on net {pin_nets[0]}")
        if kind == "opamp":
            if pin_nets[0] == pin_nets[1]:
                raise SpecError(f"{where} ({ref}): shorted plus and minus inputs")
            if pin_nets[2] == "0":
                raise SpecError(f"{where} ({ref}): output is shorted to its ground reference")
            _number(component["gain"], f"{where}.gain", positive=True)
            _coordinate(component["at"], f"{where}.at")
            for point, terminal in zip(pins, ("plus", "minus", "out")):
                required = f"{ref}.{terminal}"
                if nodes[point].get("anchor", "").casefold() != required.casefold():
                    raise SpecError(f"{where} ({ref}): pin {point} must use anchor {required}")
            if "0" in net_points:
                branches.union(pin_nets[2], "0")
        else:
            _number(component["value"], f"{where}.value", positive=kind in ("R", "C", "L"))
            if "ac" in component:
                _number(component["ac"], f"{where}.ac")
            branches.union(*pin_nets)

    for anchor, point in anchors.items():
        ref, terminal = anchor.split(".")
        if ref not in refs or refs[ref]["kind"] != "opamp":
            raise SpecError(f"nodes.{point}.anchor: no opamp exists for {anchor}")
        expected_point = refs[ref]["pins"][("plus", "minus", "out").index(terminal)]
        if point != expected_point:
            raise SpecError(f"nodes.{point}.anchor: anchor does not match the opamp's ordered pins")

    drawn = _UnionFind(nodes)
    seen_wires = set()
    for i, wire in enumerate(_list(spec["wires"], "wires")):
        if not isinstance(wire, list) or len(wire) != 2:
            raise SpecError(f"wires[{i}]: expected two point IDs")
        a, b = (point_id(p, f"wires[{i}]") for p in wire)
        if a == b:
            raise SpecError(f"wires[{i}]: a wire cannot join a point to itself")
        if nodes[a]["net"] != nodes[b]["net"]:
            raise SpecError(f"wires[{i}]: endpoints {a} and {b} declare different nets")
        key = frozenset((a, b))
        if key in seen_wires:
            raise SpecError(f"wires[{i}]: duplicate wire between {a} and {b}")
        seen_wires.add(key)
        drawn.union(a, b)
        degree.update((a, b))

    grounds = _list(spec["grounds"], "grounds")
    if not grounds:
        raise SpecError("grounds: provide at least one explicit ground point on net '0'")
    for field in ("grounds", "junctions"):
        seen = set()
        for i, point in enumerate(_list(spec[field], field)):
            point_id(point, f"{field}[{i}]")
            if point in seen:
                raise SpecError(f"{field}[{i}]: duplicate point {point}")
            seen.add(point)
            if field == "grounds":
                if nodes[point]["net"] != "0":
                    raise SpecError(f"grounds[{i}]: {point} must declare net '0'")
                drawn.union(grounds[0], point)
    for net, points in net_points.items():
        groups = defaultdict(list)
        for point in points:
            groups[drawn.find(point)].append(point)
        if len(groups) != 1:
            descriptions = [", ".join(group) for group in groups.values()]
            raise SpecError(f"net {net!r}: same-net points are disconnected in the drawing: "
                            + " | ".join(descriptions) + "; add wires or explicit grounds")

    ports = set()
    for i, port in enumerate(_list(spec["ports"], "ports")):
        _record(port, f"ports[{i}]", ("point", "label"))
        point = point_id(port["point"], f"ports[{i}].point")
        _text(port["label"], f"ports[{i}].label")
        if point in ports:
            raise SpecError(f"ports[{i}]: duplicate port point {point}")
        ports.add(point)
    for point in nodes:
        if degree[point] == 0:
            raise SpecError(f"nodes.{point}: unused isolated drawing point")
        if degree[point] == 1 and point not in ports and point not in grounds:
            raise SpecError(f"nodes.{point}: dangling endpoint; connect it or explicitly mark a port")
    for point in spec["junctions"]:
        if degree[point] < 3:
            raise SpecError(f"junctions: {point} needs at least three incident wires/component pins")
    reference = branches.find("0")
    floating = sorted(net for net in net_points if branches.find(net) != reference)
    if floating:
        raise SpecError("floating disconnected subnetwork has no component path to ground: " + ", ".join(floating))

    analysis = spec["analysis"]
    _record(analysis, "analysis", ("dc", "ac_hz", "measurements"))
    if type(analysis["dc"]) is not bool:
        raise SpecError("analysis.dc: expected true or false")
    frequencies = _list(analysis["ac_hz"], "analysis.ac_hz")
    for i, frequency in enumerate(frequencies):
        _number(frequency, f"analysis.ac_hz[{i}]", positive=True)
    if len(set(frequencies)) != len(frequencies):
        raise SpecError("analysis.ac_hz: duplicate frequencies")
    if not analysis["dc"] and not frequencies:
        raise SpecError("analysis: enable dc or provide at least one ac_hz frequency")
    names = []
    for i, measurement in enumerate(_list(analysis["measurements"], "analysis.measurements")):
        where = f"analysis.measurements[{i}]"
        _record(measurement, where, ("name", "positive", "negative"))
        name = _identifier(measurement["name"], f"{where}.name")
        if name.casefold() in {n.casefold() for n in names}:
            raise SpecError(f"{where}.name: duplicate measurement name {name}")
        names.append(name)
        for terminal in ("positive", "negative"):
            net = measurement[terminal]
            if not isinstance(net, str) or net not in net_points:
                raise SpecError(f"{where}.{terminal}: undefined net {net!r}")
        if measurement["positive"] == measurement["negative"]:
            raise SpecError(f"{where}: positive and negative must be different nets")
    if not names:
        raise SpecError("analysis.measurements: provide at least one voltage measurement")

    expected = spec["expected"]
    _record(expected, "expected", ("dc", "ac"))
    if not isinstance(expected["dc"], dict):
        raise SpecError("expected.dc: expected an object")
    dc_names = set(names) if analysis["dc"] else set()
    if set(expected["dc"]) != dc_names:
        raise SpecError("expected.dc: keys must match all DC measurement names (or be empty when dc is false)")
    for name, value in expected["dc"].items():
        _number(value, f"expected.dc.{name}")
    expected_frequencies = set()
    for i, entry in enumerate(_list(expected["ac"], "expected.ac")):
        where = f"expected.ac[{i}]"
        _record(entry, where, ("frequency", "values"))
        frequency = _number(entry["frequency"], f"{where}.frequency", positive=True)
        if frequency in expected_frequencies:
            raise SpecError(f"{where}.frequency: duplicate expected frequency")
        expected_frequencies.add(frequency)
        if not isinstance(entry["values"], dict) or set(entry["values"]) != set(names):
            raise SpecError(f"{where}.values: keys must match all measurement names")
        for name, value in entry["values"].items():
            if not isinstance(value, list) or len(value) != 2:
                raise SpecError(f"{where}.values.{name}: expected [real, imaginary]")
            for part in value:
                _number(part, f"{where}.values.{name}")
            _number(math.hypot(*value), f"{where}.values.{name} complex magnitude")
    if expected_frequencies != set(frequencies):
        raise SpecError("expected.ac: frequencies must exactly match analysis.ac_hz")


def _spice_number(value):
    return format(float(value), ".17g")


def spice_netlist(spec: dict, analysis: str | float = "dc") -> str:
    """Produce one ideal linear ngspice operating-point or AC analysis."""
    validate_spec(spec)
    if analysis == "dc":
        directive = ".op"
    else:
        frequency = _number(analysis, "SPICE AC frequency", positive=True)
        directive = f".ac lin 1 {_spice_number(frequency)} {_spice_number(frequency)}"
    lines = [f"{spec['id']}: {spec['title']}",
             "* Ideal linear signal model; opamps have no supply or output limits."]
    for component in spec["components"]:
        nets = [spec["nodes"][point]["net"] for point in component["pins"]]
        kind, ref = component["kind"], component["ref"]
        if kind == "opamp":
            lines.append(f"E{ref} {nets[2]} 0 {nets[0]} {nets[1]} {_spice_number(component['gain'])}")
        elif kind in ("V", "I"):
            lines.append(f"{ref} {' '.join(nets)} DC {_spice_number(component['value'])}"
                         f" AC {_spice_number(component.get('ac', 0))}")
        else:
            lines.append(f"{ref} {' '.join(nets)} {_spice_number(component['value'])}")
    lines.extend((directive, ".control", "set filetype=ascii", "set numdgt=15", "run",
                  "write result.raw all", "quit", ".endc", ".end", ""))
    return "\n".join(lines)


@dataclass(frozen=True)
class RawPlot:
    name: str
    flags: tuple[str, ...]
    variables: tuple[str, ...]
    points: tuple[tuple[complex, ...], ...]


def _raw_number(token, is_complex, where):
    token = token.strip().replace("D", "e").replace("d", "e")
    try:
        if is_complex:
            parts = token.split(",")
            if len(parts) != 2:
                raise ValueError("expected real,imaginary")
            result = complex(float(parts[0]), float(parts[1]))
        else:
            result = complex(float(token), 0)
    except ValueError as exc:
        raise SimulationError(f"raw output {where}: malformed numeric value {token!r}") from exc
    if not (math.isfinite(result.real) and math.isfinite(result.imag)):
        raise SimulationError(f"raw output {where}: nonfinite value {token!r}")
    return result


def parse_raw(text: str) -> list[RawPlot]:
    """Parse one or more ngspice ASCII raw plots, checking every sample.

    Variables retain their simulator names, including v(node), i(vsource), and
    branch-current forms. Comparison later looks up voltage vectors by name,
    never by their position in the file.
    """
    if not isinstance(text, str) or not text.strip():
        raise SimulationError("raw output is empty or not text")
    lines = text.lstrip("\ufeff").splitlines()
    cursor = 0
    plots = []
    while cursor < len(lines):
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        if cursor == len(lines):
            break
        header = {}
        while cursor < len(lines):
            line = lines[cursor].strip()
            cursor += 1
            if not line:
                continue
            if ":" not in line:
                raise SimulationError(f"raw output line {cursor}: malformed header")
            key, value = line.split(":", 1)
            key = key.strip().casefold()
            if key == "variables":
                break
            if key == "binary":
                raise SimulationError("raw output is binary; ASCII output is required")
            if key in header:
                raise SimulationError(f"raw output: duplicate header {key}")
            header[key] = value.strip()
        else:
            raise SimulationError("raw output: missing Variables section")
        try:
            count = int(header["no. variables"])
            npoints = int(header["no. points"])
            name = header["plotname"]
            flags = tuple(header["flags"].casefold().split())
        except (KeyError, ValueError) as exc:
            raise SimulationError("raw output: missing or invalid plot metadata") from exc
        if count <= 0 or npoints <= 0 or not name:
            raise SimulationError("raw output: plot must have variables, points, and a name")
        if ("complex" in flags) == ("real" in flags):
            raise SimulationError("raw output: Flags must specify exactly one of real or complex")
        if "unpadded" in flags:
            raise SimulationError("raw output: unpadded vectors are unsupported")
        variables = []
        for index in range(count):
            if cursor >= len(lines):
                raise SimulationError("raw output: truncated variable table")
            fields = lines[cursor].split()
            cursor += 1
            if len(fields) < 3 or fields[0] != str(index):
                raise SimulationError(f"raw output line {cursor}: malformed variable table")
            if fields[1].casefold() in {v.casefold() for v in variables}:
                raise SimulationError(f"raw output: duplicate variable {fields[1]}")
            variables.append(fields[1])
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        if cursor >= len(lines) or lines[cursor].strip().casefold() != "values:":
            raise SimulationError("raw output: missing ASCII Values section")
        cursor += 1
        points = []
        for index in range(npoints):
            values = []
            for variable in range(count):
                while cursor < len(lines) and not lines[cursor].strip():
                    cursor += 1
                if cursor >= len(lines):
                    raise SimulationError("raw output: truncated Values section")
                line = lines[cursor].strip()
                cursor += 1
                if variable == 0:
                    fields = line.split(None, 1)
                    if len(fields) != 2 or fields[0] != str(index):
                        raise SimulationError(f"raw output line {cursor}: invalid sample index")
                    line = fields[1]
                values.append(_raw_number(line, "complex" in flags, f"line {cursor}"))
            points.append(tuple(values))
        plots.append(RawPlot(name, flags, tuple(variables), tuple(points)))
    if not plots:
        raise SimulationError("raw output contains no plots")
    return plots


def _measure(plot: RawPlot, measurements):
    if len(plot.points) != 1:
        raise SimulationError(f"expected one simulation point, got {len(plot.points)}")
    vectors = dict(zip((v.casefold() for v in plot.variables), plot.points[0]))

    def voltage(net):
        if net == "0":
            return 0j
        key = f"v({net})".casefold()
        if key not in vectors:
            raise SimulationError(f"raw output is missing voltage vector {key}")
        return vectors[key]

    return {m["name"]: voltage(m["positive"]) - voltage(m["negative"])
            for m in measurements}


_SIM_ERROR = re.compile(
    r"^\s*(?:error\b|fatal\b|doanalyses:|warning:\s*singular matrix)"
    r"|\bsimulation(?:\(s\)|s)?\s+aborted\b|\bno such vector\b"
    r"|\bno data (?:saved|written)\b|\btimestep too small\b",
    re.IGNORECASE | re.MULTILINE,
)


def _execute(executable, netlist, raw_path, log_path, timeout):
    raw_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix=".spice-", dir=netlist.parent) as temporary:
        raw = Path(temporary) / "result.raw"
        try:
            process = subprocess.run([executable, "-b", str(netlist)], cwd=temporary,
                                     capture_output=True, text=True, errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            chunks = [exc.stdout or "", exc.stderr or ""]
            output = "\n".join(c.decode(errors="replace") if isinstance(c, bytes) else c for c in chunks)
            log_path.write_text(output + f"\nERROR: ngspice timed out after {timeout} seconds\n", encoding="utf-8")
            raise SimulationError(f"ngspice timed out after {timeout} seconds") from exc
        except OSError as exc:
            log_path.write_text(f"ERROR: cannot execute ngspice: {exc}\n", encoding="utf-8")
            raise SimulationError(f"cannot execute ngspice: {exc}") from exc
        finally:
            if raw.is_file():
                shutil.move(str(raw), str(raw_path))
        output = process.stdout + "\n" + process.stderr
        log_path.write_text(output, encoding="utf-8")
        if process.returncode != 0:
            raise SimulationError(f"ngspice exited with status {process.returncode}; see {log_path.name}")
        error = _SIM_ERROR.search(output)
        if error:
            line = output[error.start():].splitlines()[0].strip()
            raise SimulationError(f"ngspice reported an error despite exit status 0: {line}")
        if not raw_path.is_file():
            raise SimulationError("ngspice did not create result.raw")


def _simulator_info(executable, timeout):
    info = {"executable": executable, "version": None}
    if executable is None:
        return info
    try:
        result = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                errors="replace", timeout=min(timeout, 10))
        banner = (result.stdout + "\n" + result.stderr).strip()
        match = re.search(r"ngspice[- ]+([0-9][^\s:]*)", banner, re.IGNORECASE)
        info.update(version=match.group(1) if match else None,
                    version_output=banner, version_exit_code=result.returncode)
    except (OSError, subprocess.TimeoutExpired) as exc:
        info["version_error"] = str(exc)
    return info


def simulate(spec: dict, output_dir, executable="ngspice", timeout=30) -> dict[str, Any]:
    """Run all requested analyses and compare independent expected voltages.

    Return a JSON-serializable passing report. On simulator/output/comparison
    failure, save report.json and raise SimulationError with report attached.
    Invalid specifications raise SpecError before any simulator is launched.
    Reusing output_dir replaces artifacts with the same analysis names.
    """
    validate_spec(spec)
    _number(timeout, "timeout", positive=True)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.json"
    report = {"case_id": spec["id"], "title": spec["title"], "status": "pass",
              "model": "ideal linear components; signal-only finite-gain opamps",
              "tolerances": {"absolute_v": ABS_TOL_V, "relative": REL_TOL},
              "runs": [], "errors": []}
    program = shutil.which(str(executable))
    if program is not None:
        program = str(Path(program).resolve())
    report["simulator"] = _simulator_info(program, timeout)
    report["spec_sha256"] = hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    analyses = []
    if spec["analysis"]["dc"]:
        analyses.append(("dc", "dc", spec["expected"]["dc"]))
    expected_ac = {entry["frequency"]: entry["values"] for entry in spec["expected"]["ac"]}
    analyses.extend((f"ac_{i:03d}", frequency, expected_ac[frequency])
                    for i, frequency in enumerate(spec["analysis"]["ac_hz"]))
    for basename, analysis, expected in analyses:
        is_dc = analysis == "dc"
        netlist = output_dir / f"{basename}.cir"
        raw_path = output_dir / f"{basename}.raw"
        log_path = output_dir / f"{basename}.log"
        run = {"analysis": "dc" if is_dc else "ac", "frequency_hz": None if is_dc else analysis,
               "status": "pass", "artifacts": {"netlist": netlist.name, "raw": raw_path.name,
                                                "log": log_path.name}, "measurements": {}}
        report["runs"].append(run)
        try:
            netlist.write_text(spice_netlist(spec, analysis), encoding="utf-8")
            if program is None:
                raw_path.unlink(missing_ok=True)
                message = f"ngspice executable not found: {executable}"
                log_path.write_text("ERROR: " + message + "\n", encoding="utf-8")
                raise SimulationError(message)
            _execute(program, netlist, raw_path, log_path, timeout)
            plots = parse_raw(raw_path.read_text(encoding="utf-8"))
            wanted = "operating point" if is_dc else "ac analysis"
            matches = [plot for plot in plots if plot.name.casefold() == wanted]
            if len(matches) != 1:
                raise SimulationError(f"raw output: expected exactly one {wanted} plot, found {len(matches)}")
            plot = matches[0]
            if ("complex" in plot.flags) != (not is_dc):
                raise SimulationError("raw output: real/complex Flags disagree with requested analysis")
            if not is_dc:
                vectors = {name.casefold(): i for i, name in enumerate(plot.variables)}
                if "frequency" not in vectors or len(plot.points) != 1:
                    raise SimulationError("raw AC output is missing its single frequency sample")
                frequency = plot.points[0][vectors["frequency"]]
                if frequency.imag != 0 or frequency.real <= 0 or not math.isclose(
                        frequency.real, analysis, rel_tol=1e-9, abs_tol=0):
                    raise SimulationError(f"raw AC output frequency {frequency} does not match requested {analysis}")
            actuals = _measure(plot, spec["analysis"]["measurements"])
            for name, actual in actuals.items():
                target = complex(expected[name]) if is_dc else complex(*expected[name])
                if not math.isfinite(math.hypot(actual.real, actual.imag)):
                    raise SimulationError(f"measurement {name}: nonfinite voltage difference")
                difference = actual - target
                error = math.hypot(difference.real, difference.imag)
                if not math.isfinite(error):
                    raise SimulationError(f"measurement {name}: nonfinite comparison error")
                allowed = ABS_TOL_V + REL_TOL * math.hypot(target.real, target.imag)
                passed = error <= allowed
                run["measurements"][name] = {
                    "actual": actual.real if is_dc else [actual.real, actual.imag],
                    "expected": expected[name], "absolute_error_v": error,
                    "allowed_error_v": allowed, "passed": passed,
                }
                if not passed:
                    run["status"] = "fail"
                    report["errors"].append(f"{basename}: {name} voltage mismatch: actual {actual}, expected {target}")
        except (SimulationError, OSError, UnicodeError) as exc:
            run["status"] = "fail"
            run["error"] = str(exc)
            report["errors"].append(f"{basename}: {exc}")
    if report["errors"]:
        report["status"] = "fail"
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if report["status"] == "fail":
        raise SimulationError("; ".join(report["errors"]), report=report, report_path=report_path)
    return report


def _json_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise SpecError(f"JSON contains duplicate object key {key!r}")
        obj[key] = value
    return obj


def load_spec(path) -> dict:
    """Load JSON without silently accepting repeated object keys."""
    try:
        with Path(path).open(encoding="utf-8") as stream:
            return json.load(stream, object_pairs_hook=_json_object)
    except json.JSONDecodeError as exc:
        raise SpecError(f"{path}: invalid JSON: {exc}") from exc


def _print_message(message, *, file=None):
    """Keep Unicode paths and diagnostics usable on an ASCII-only console."""
    stream = sys.stdout if file is None else file
    encoding = getattr(stream, "encoding", None)
    if encoding:
        message = message.encode(encoding, errors="backslashreplace").decode(encoding)
    print(message, file=stream)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path, help="circuit schema JSON file")
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for netlists, raw output, logs, and report")
    parser.add_argument("--check-only", action="store_true", help="validate schema and connectivity without launching ngspice")
    parser.add_argument("--ngspice", default="ngspice", help="ngspice executable name or path")
    parser.add_argument("--timeout", type=float, default=30, help="timeout in seconds per analysis")
    args = parser.parse_args(argv)
    try:
        spec = load_spec(args.case)
        if args.check_only:
            validate_spec(spec)
            _print_message(f"PASS {spec['id']}: schema and drawn connectivity")
        else:
            result = simulate(spec, args.output_dir, executable=args.ngspice, timeout=args.timeout)
            _print_message(f"PASS {result['case_id']}: {len(result['runs'])} independent SPICE comparisons; {args.output_dir / 'report.json'}")
    except (SpecError, SimulationError, OSError) as exc:
        _print_message(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
