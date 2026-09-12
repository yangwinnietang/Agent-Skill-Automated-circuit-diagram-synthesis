"""Structural faults, simulator failures, and independent-value comparisons."""

from copy import deepcopy
import json
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import electrical as ec


def divider():
    # Independent expectation: 12 V * 1 kohm / (2 kohm + 1 kohm) = 4 V.
    return {
        "id": "divider", "title": "Resistor divider", "category": "passive",
        "nodes": {
            "s": {"net": "vin", "at": [0, 3]},
            "o": {"net": "out", "at": [3, 3]},
            "g": {"net": "0", "at": [0, 0]},
            "g2": {"net": "0", "at": [3, 0]},
        },
        "components": [
            {"ref": "V1", "kind": "V", "value": 12, "ac": 1, "pins": ["s", "g"]},
            {"ref": "R1", "kind": "R", "value": 2000, "pins": ["s", "o"]},
            {"ref": "R2", "kind": "R", "value": 1000, "pins": ["o", "g2"]},
        ],
        "wires": [], "grounds": ["g", "g2"], "junctions": [],
        "ports": [{"point": "o", "label": "Vout"}],
        "analysis": {"dc": True, "ac_hz": [1000], "measurements": [
            {"name": "Vin", "positive": "vin", "negative": "0"},
            {"name": "Vout", "positive": "out", "negative": "0"},
            {"name": "Drop", "positive": "vin", "negative": "out"},
        ]},
        "expected": {"dc": {"Vin": 12, "Vout": 4, "Drop": 8}, "ac": [
            {"frequency": 1000, "values": {"Vin": [1, 0], "Vout": [1 / 3, 0], "Drop": [2 / 3, 0]}}
        ]},
    }


def raw_plot(name="Operating Point", complex_values=False, *, out=4, vin=12, frequency=1000):
    variables = ["V(OUT)", "i(v1)", "v(vin)"]
    values = [complex(out), complex(-0.004), complex(vin)]
    if complex_values:
        variables.insert(0, "frequency")
        values.insert(0, complex(frequency))
    lines = ["Title: independent fixture", "Date: fixture", f"Plotname: {name}",
             "Flags: " + ("complex" if complex_values else "real"),
             f"No. Variables: {len(variables)}", "No. Points: 1", "Variables:"]
    for i, variable in enumerate(variables):
        lines.append(f"\t{i}\t{variable}\t{'frequency' if variable == 'frequency' else 'voltage'}")
    lines.append("Values:")
    for i, value in enumerate(values):
        token = f"{value.real:.16e},{value.imag:.16e}" if complex_values else f"{value.real:.16e}"
        lines.append(("0\t" if i == 0 else "\t") + token)
    return "\n".join(lines) + "\n"


class ValidationTests(unittest.TestCase):
    def test_valid_divider_and_separate_grounds(self):
        ec.validate_spec(divider())

    def test_same_net_requires_drawn_connection(self):
        spec = divider()
        spec["nodes"]["remote"] = {"net": "out", "at": [6, 3]}
        spec["ports"].append({"point": "remote", "label": "remote"})
        with self.assertRaisesRegex(ec.SpecError, "same-net points are disconnected"):
            ec.validate_spec(spec)
        spec["wires"].append(["o", "remote"])
        ec.validate_spec(spec)

    def test_ground_symbol_is_required_on_each_separate_ground_wire_group(self):
        spec = divider()
        spec["grounds"].remove("g2")
        with self.assertRaisesRegex(ec.SpecError, "same-net points are disconnected"):
            ec.validate_spec(spec)
        spec["wires"].append(["g", "g2"])
        ec.validate_spec(spec)

    def test_malformed_and_unknown_fields_are_rejected(self):
        mutations = [
            (lambda s: s.update(extra=1), "unknown fields"),
            (lambda s: s.pop("expected"), "missing fields"),
            (lambda s: s.update(id="bad;quit"), "invalid identifier"),
            (lambda s: s.update(title="title\n.end"), "single-line"),
            (lambda s: s["components"][0].update(kind="diode"), "unsupported component"),
            (lambda s: s["components"].append([]), "expected an object"),
            (lambda s: s["components"][1].update(ac=1), "unknown fields"),
            (lambda s: s["components"][1].update(label_side="left"), "above or below"),
            (lambda s: s["components"][1].update(ref="C1"), "reference must start"),
            (lambda s: s["components"][2].update(ref="r1"), "duplicate reference"),
            (lambda s: s["components"][0].update(pins=["s"]), "ordered pins"),
            (lambda s: s["components"][0].update(pins=["s", "missing"]), "undefined point"),
            (lambda s: s["nodes"]["o"].update(at=[1]), "expected \\[x, y\\]"),
            (lambda s: s["nodes"]["o"].update(anchor="U1.out"), "exactly one"),
            (lambda s: s["nodes"]["o"].update(at=[0, 3]), "coincides"),
            (lambda s: s["wires"].append(["s", "o"]), "different nets"),
            (lambda s: s["wires"].append(["s", "s"]), "point to itself"),
            (lambda s: s["grounds"].append("s"), "must declare net '0'"),
            (lambda s: s["grounds"].clear(), "explicit ground"),
            (lambda s: s["junctions"].append("o"), "three incident"),
            (lambda s: s["ports"][0].update(point="missing"), "undefined point"),
            (lambda s: s["analysis"].update(dc=1), "true or false"),
            (lambda s: s["analysis"]["measurements"][0].update(positive="missing"), "undefined net"),
            (lambda s: s["analysis"]["measurements"][0].update(negative="vin"), "different nets"),
            (lambda s: s["analysis"].update(ac_hz=[1000, 1000]), "duplicate frequencies"),
            (lambda s: s["expected"]["dc"].pop("Vin"), "match all DC"),
            (lambda s: s["expected"]["ac"][0]["values"].pop("Vin"), "match all measurement"),
            (lambda s: s["expected"]["ac"][0].update(frequency=999), "exactly match"),
            (lambda s: s["expected"]["ac"][0]["values"].update(Vin=[1]), "real, imaginary"),
        ]
        for mutate, message in mutations:
            with self.subTest(message=message):
                spec = divider()
                mutate(spec)
                with self.assertRaisesRegex(ec.SpecError, message):
                    ec.validate_spec(spec)

    def test_finite_numbers_and_positive_passives(self):
        for value in (0, -1, True, "1k", float("inf"), float("nan"), 10**1000):
            with self.subTest(value=repr(value)[:40]):
                spec = divider()
                spec["components"][1]["value"] = value
                with self.assertRaisesRegex(ec.SpecError, "finite positive"):
                    ec.validate_spec(spec)
        for value in (True, "1", float("nan"), float("inf")):
            spec = divider()
            spec["components"][0]["ac"] = value
            with self.assertRaisesRegex(ec.SpecError, "finite number"):
                ec.validate_spec(spec)
        spec = divider()
        spec["components"][0]["value"] = -12
        spec["components"][0]["ac"] = -1
        ec.validate_spec(spec)

    def test_case_insensitive_net_collision(self):
        spec = divider()
        spec["nodes"]["copy"] = {"net": "OUT", "at": [6, 3]}
        with self.assertRaisesRegex(ec.SpecError, "collide in SPICE"):
            ec.validate_spec(spec)

    def test_shorted_terminals(self):
        spec = divider()
        spec["components"][1]["pins"] = ["s", "s"]
        with self.assertRaisesRegex(ec.SpecError, "shorted component terminals"):
            ec.validate_spec(spec)

    def test_dangling_and_isolated_points(self):
        spec = divider()
        spec["nodes"]["loose"] = {"net": "out", "at": [6, 3]}
        spec["wires"].append(["o", "loose"])
        with self.assertRaisesRegex(ec.SpecError, "dangling endpoint"):
            ec.validate_spec(spec)
        spec = divider()
        spec["nodes"]["loose"] = {"net": "unused", "at": [6, 3]}
        with self.assertRaisesRegex(ec.SpecError, "unused isolated"):
            ec.validate_spec(spec)

    def test_disconnected_network_even_with_no_dangling_terminals(self):
        spec = divider()
        spec["nodes"].update(a={"net": "floating_a", "at": [6, 0]},
                             b={"net": "floating_b", "at": [6, 3]})
        spec["components"].extend([
            {"ref": "V2", "kind": "V", "value": 1, "pins": ["a", "b"]},
            {"ref": "R3", "kind": "R", "value": 1000, "pins": ["a", "b"]},
        ])
        with self.assertRaisesRegex(ec.SpecError, "floating disconnected subnetwork"):
            ec.validate_spec(spec)

    def test_opamp_anchors_and_feedback_share_the_same_pin_model(self):
        spec = divider()
        spec["nodes"].update(plus={"net": "vin", "anchor": "U1.plus"},
                             minus={"net": "buffered", "anchor": "U1.minus"},
                             output={"net": "buffered", "anchor": "U1.out"},
                             tip={"net": "buffered", "at": [7, 3]})
        spec["components"].append({"ref": "U1", "kind": "opamp", "gain": 1e6,
                                    "pins": ["plus", "minus", "output"], "at": [5, 3]})
        spec["wires"].extend([["s", "plus"], ["minus", "tip"], ["output", "tip"]])
        ec.validate_spec(spec)
        self.assertIn("EU1 buffered 0 vin buffered 1000000", ec.spice_netlist(spec))
        spec["components"][-1]["pins"] = ["minus", "plus", "output"]
        with self.assertRaisesRegex(ec.SpecError, "must use anchor"):
            ec.validate_spec(spec)

    def test_no_silent_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"id": "a", "id": "b"}')
            with self.assertRaisesRegex(ec.SpecError, "duplicate object key"):
                ec.load_spec(path)


class NetlistTests(unittest.TestCase):
    def test_source_polarity_and_passive_pin_order(self):
        spec = divider()
        netlist = ec.spice_netlist(spec)
        self.assertIn("V1 vin 0 DC 12 AC 1\n", netlist)
        self.assertIn("R1 vin out 2000\n", netlist)
        self.assertIn(".op\n.control\n", netlist)
        self.assertIn("set filetype=ascii\n", netlist)
        self.assertTrue(netlist.endswith("quit\n.endc\n.end\n"))
        spec["components"][0].update(kind="I", ref="I1")
        self.assertIn("I1 vin 0 DC 12 AC 1\n", ec.spice_netlist(spec))

    def test_ac_and_invalid_analysis(self):
        self.assertIn(".ac lin 1 1000 1000\n", ec.spice_netlist(divider(), 1000))
        for analysis in (".end", 0, -1, True, float("nan")):
            with self.assertRaises(ec.SpecError):
                ec.spice_netlist(divider(), analysis)


class RawParserTests(unittest.TestCase):
    def test_real_complex_multiple_plots_and_variable_order(self):
        text = raw_plot() + "\n" + raw_plot("AC Analysis", True, out=0.2-0.3j, vin=1)
        plots = ec.parse_raw(text)
        self.assertEqual(len(plots), 2)
        self.assertEqual(plots[0].variables[0], "V(OUT)")
        measured = ec._measure(plots[1], divider()["analysis"]["measurements"])
        self.assertEqual(measured["Vout"], 0.2-0.3j)
        self.assertAlmostEqual(measured["Drop"], 0.8+0.3j)

    def test_malformed_raw_is_rejected(self):
        cases = [
            ("", "empty"),
            ("Title: fixture\n", "missing Variables"),
            (raw_plot().replace("No. Points: 1", "No. Points: 0"), "plot must have"),
            (raw_plot().replace("Flags: real", "Flags: complex real"), "Flags"),
            (raw_plot().replace("Values:", "Binary:"), "ASCII Values"),
            (raw_plot().replace("\t1\ti(v1)", "\t2\ti(v1)"), "variable table"),
            (raw_plot().replace("i(v1)", "v(out)"), "duplicate variable"),
            (raw_plot().replace("0\t4.0000000000000000e+00", "2\t4.0"), "sample index"),
            (raw_plot().replace("4.0000000000000000e+00", "NaN"), "nonfinite"),
            (raw_plot().replace("4.0000000000000000e+00", "Infinity"), "nonfinite"),
            (raw_plot().replace("4.0000000000000000e+00", "1;quit"), "malformed numeric"),
            (raw_plot().rsplit("\n", 2)[0], "truncated Values"),
            (raw_plot("AC Analysis", True).replace("4.0000000000000000e+00,0.0000000000000000e+00", "4.0"), "malformed numeric"),
        ]
        for text, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ec.SimulationError, message):
                    ec.parse_raw(text)

    def test_fortran_exponents(self):
        plot = ec.parse_raw(raw_plot().replace("e+", "D+"))[0]
        self.assertEqual(plot.points[0][0], 4)


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "result"
        self.mode = "pass"
        self.actual_frequency = 1000
        self.spec = divider()
        self.commands = []
        # Use the same canonical native spelling returned after tool discovery;
        # Windows resolves a POSIX-rooted /tools path onto the current drive.
        self.executable = str(Path(self.temp.name).resolve() / "tools" / "ngspice")
        self.which = patch.object(ec.shutil, "which", return_value=self.executable)
        self.which_mock = self.which.start()
        self.addCleanup(self.which.stop)
        self.runner = patch.object(ec.subprocess, "run", side_effect=self.fake_run)
        self.runner.start()
        self.addCleanup(self.runner.stop)

    def fake_run(self, command, **kwargs):
        self.commands.append(command)
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "ngspice-45 : Circuit level simulation program", "")
        self.assertEqual(command[:2], [self.executable, "-b"])
        netlist = Path(command[-1]).read_text()
        ac = ".ac lin" in netlist
        if self.mode == "timeout":
            raise subprocess.TimeoutExpired(command, 1, output=b"partial simulator output")
        if self.mode == "os-error":
            raise OSError("cannot launch")
        if self.mode != "missing":
            out = (1 / 3 if ac else 4) if self.mode != "mismatch" else 17
            raw = raw_plot("AC Analysis" if ac else "Operating Point", ac,
                           out=out, vin=1 if ac else 12,
                           frequency=2000 if self.mode == "wrong-frequency" else self.actual_frequency)
            if self.mode == "malformed":
                raw = "not a raw file"
            elif self.mode == "nonfinite":
                raw = raw.replace("4.0000000000000000e+00", "nan")
            elif self.mode == "missing-voltage":
                raw = raw.replace("V(OUT)", "v(other)")
            elif self.mode == "wrong-plot":
                raw = raw.replace("Operating Point", "Transient Analysis").replace("AC Analysis", "Transient Analysis")
            (Path(kwargs["cwd"]) / "result.raw").write_text(raw)
        message = {
            "exit-zero-error": "Error: unknown device",
            "singular": "Warning: singular matrix: check node out",
            "aborted": "doAnalyses: AC: no data saved for A.C. analysis; simulation(s) aborted",
        }.get(self.mode, "simulation completed")
        return subprocess.CompletedProcess(command, 7 if self.mode == "nonzero" else 0, message, "")

    def test_runs_dc_ac_compares_differential_and_records_provenance(self):
        report = ec.simulate(self.spec, self.output)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["simulator"]["version"], "45")
        self.assertEqual(len(report["spec_sha256"]), 64)
        self.assertEqual(report["runs"][0]["measurements"]["Drop"]["actual"], 8)
        self.assertAlmostEqual(report["runs"][1]["measurements"]["Drop"]["actual"][0], 2 / 3)
        for base in ("dc", "ac_000"):
            for extension in ("cir", "raw", "log"):
                self.assertTrue((self.output / f"{base}.{extension}").is_file())
        self.assertEqual(json.loads((self.output / "report.json").read_text()), report)

    def test_process_and_output_failures_always_save_failing_reports(self):
        modes = ("missing", "mismatch", "malformed", "nonfinite", "missing-voltage",
                 "wrong-plot", "wrong-frequency", "exit-zero-error", "singular", "aborted",
                 "nonzero", "timeout", "os-error")
        for mode in modes:
            with self.subTest(mode=mode):
                self.mode = mode
                with self.assertRaises(ec.SimulationError) as raised:
                    ec.simulate(self.spec, self.output)
                report = json.loads((self.output / "report.json").read_text())
                self.assertEqual(report["status"], "fail")
                self.assertTrue(report["errors"])
                self.assertEqual(raised.exception.report, report)
                self.assertTrue((self.output / "dc.log").is_file())

    def test_stale_raw_cannot_make_missing_output_pass(self):
        ec.simulate(self.spec, self.output)
        self.mode = "missing"
        with self.assertRaisesRegex(ec.SimulationError, "did not create result.raw"):
            ec.simulate(self.spec, self.output)
        self.assertFalse((self.output / "dc.raw").exists())

    def test_tiny_ac_frequency_must_match_relative_scale(self):
        self.spec["analysis"]["ac_hz"] = [1e-15]
        self.spec["expected"]["ac"][0]["frequency"] = 1e-15
        for actual in (1e-20, 0, -1e-15):
            with self.subTest(actual_frequency=actual):
                self.actual_frequency = actual
                with self.assertRaisesRegex(ec.SimulationError, "frequency.*does not match"):
                    ec.simulate(self.spec, self.output)
        self.actual_frequency = 1e-15
        self.assertEqual(ec.simulate(self.spec, self.output)["status"], "pass")

    def test_missing_executable(self):
        self.which_mock.return_value = None
        with self.assertRaisesRegex(ec.SimulationError, "executable not found"):
            ec.simulate(self.spec, self.output)
        self.assertFalse(self.commands)
        self.assertEqual(json.loads((self.output / "report.json").read_text())["status"], "fail")

    def test_invalid_spec_never_launches_simulator(self):
        self.spec["expected"]["dc"].clear()
        with self.assertRaises(ec.SpecError):
            ec.simulate(self.spec, self.output)
        self.assertFalse(self.commands)

    def test_check_only_never_launches_simulator(self):
        path = Path(self.temp.name) / "case.json"
        path.write_text(json.dumps(self.spec))
        self.assertEqual(ec.main([str(path), "--output-dir", str(self.output), "--check-only"]), 0)
        self.assertFalse(self.commands)

    def test_unicode_output_path_on_ascii_console(self):
        path = Path(self.temp.name) / "case.json"
        path.write_text(json.dumps(self.spec))
        output = self.output / "验证"
        buffer = io.BytesIO()
        with io.TextIOWrapper(buffer, encoding="ascii") as stream:
            with patch.object(ec.sys, "stdout", stream):
                self.assertEqual(ec.main([str(path), "--output-dir", str(output)]), 0)
            stream.flush()
            self.assertIn(b"PASS divider", buffer.getvalue())
        self.assertTrue((output / "report.json").is_file())


@unittest.skipUnless(os.environ.get("CIRCUIT_RUN_SPICE") == "1", "set CIRCUIT_RUN_SPICE=1 for real ngspice")
class RealSpiceTests(unittest.TestCase):
    def test_independent_divider_values_and_repository_cases(self):
        executable = os.environ.get("NGSPICE", "ngspice")
        cases = [divider()]
        cases.extend(ec.load_spec(path) for path in sorted((ROOT / "assets" / "verified-circuits").glob("*.json")))
        with tempfile.TemporaryDirectory() as directory:
            for index, spec in enumerate(cases):
                with self.subTest(case=spec["id"]):
                    report = ec.simulate(spec, Path(directory) / f"{index:03d}", executable=executable)
                    self.assertEqual(report["status"], "pass")

    def test_polarity_measurement_and_removed_load_mutations_fail(self):
        source_reversed = divider()
        source_reversed["components"][0]["pins"].reverse()
        measurement_reversed = divider()
        measurement = measurement_reversed["analysis"]["measurements"][1]
        measurement["positive"], measurement["negative"] = measurement["negative"], measurement["positive"]

        loaded = divider()
        loaded["components"].append({"ref": "Rload", "kind": "R", "value": 1000, "pins": ["o", "g2"]})
        # Independent parallel-load result: 12 * 500 / (2000 + 500) = 2.4 V.
        loaded["expected"]["dc"].update(Vout=2.4, Drop=9.6)
        loaded["expected"]["ac"][0]["values"].update(Vout=[0.2, 0], Drop=[0.8, 0])
        removed_load = deepcopy(loaded)
        removed_load["components"].pop()
        executable = os.environ.get("NGSPICE", "ngspice")
        with tempfile.TemporaryDirectory() as directory:
            ec.simulate(loaded, Path(directory) / "loaded", executable=executable)
            for name, spec in (("source_polarity", source_reversed),
                               ("measurement_polarity", measurement_reversed),
                               ("removed_load", removed_load)):
                with self.subTest(mutation=name):
                    ec.validate_spec(spec)
                    with self.assertRaisesRegex(ec.SimulationError, "voltage mismatch") as raised:
                        ec.simulate(spec, Path(directory) / name, executable=executable)
                    self.assertEqual(raised.exception.report["status"], "fail")


if __name__ == "__main__":
    unittest.main()
