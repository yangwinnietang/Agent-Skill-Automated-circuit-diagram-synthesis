"""Independent circuit-oracle checks and bounded, real-ngspice variation tests.

The oracle was derived independently of the renderer and SPICE exporter. These
tests compare ordered terminals, values, measurements, and calculated voltages;
rendering successfully is never taken as evidence of electrical correctness.

Set CIRCUIT_RUN_SPICE=1 to require ngspice and run 24 gallery analyses, 30
parameter-variation analyses, and 5 deliberately incorrect circuit analyses.
The opamp checks cover a static finite-gain VCVS model, not physical stability.
"""

from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import electrical as ec

CASE_DIR = ROOT / "assets" / "verified-circuits"
ORACLE_PATH = ROOT / "tests" / "oracles" / "electrical-ground-truth.json"
CASE_IDS = frozenset((
    "divider-unloaded", "divider-loaded", "parallel-current",
    "bridge-balanced", "bridge-unbalanced", "rc-lowpass", "rc-highpass",
    "rl-lowpass", "series-rlc", "opamp-inverting", "opamp-noninverting",
    "opamp-summer",
))


def load_case(case_id):
    return ec.load_spec(CASE_DIR / (case_id + ".json"))


def load_oracles():
    document = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    return {case["id"].replace("_", "-"): case for case in document["circuits"]}


def components_by_ref(spec):
    return {component["ref"]: component for component in spec["components"]}


def measured_values(spec, voltages):
    """Project independently calculated node voltages onto declared probes."""
    return {m["name"]: voltages[m["positive"]] - voltages[m["negative"]]
            for m in spec["analysis"]["measurements"]}


def dc_only(spec, voltages):
    spec["analysis"]["dc"] = True
    spec["analysis"]["ac_hz"] = []
    spec["expected"] = {"dc": measured_values(spec, voltages), "ac": []}
    return spec


def ac_only(spec, frequency, voltages):
    spec["analysis"]["dc"] = False
    spec["analysis"]["ac_hz"] = [frequency]
    values = measured_values(spec, voltages)
    spec["expected"] = {
        "dc": {}, "ac": [{"frequency": frequency, "values": {
            name: [complex(value).real, complex(value).imag]
            for name, value in values.items()}}],
    }
    return spec


def filter_voltages(case_id, values, frequency, source=1):
    """Independent complex-impedance equations, including internal RLC nodes."""
    jw = 2j * math.pi * frequency
    result = {"0": 0j, "vin": complex(source)}
    if case_id == "rc-lowpass":
        result["out"] = source / (1 + jw * values["R1"] * values["C1"])
    elif case_id == "rc-highpass":
        x = jw * values["R1"] * values["C1"]
        result["out"] = source * x / (1 + x)
    elif case_id == "rl-lowpass":
        result["out"] = source * values["R1"] / (values["R1"] + jw * values["L1"])
    elif case_id == "series-rlc":
        zc = 1 / (jw * values["C1"])
        zl = jw * values["L1"]
        current = source / (values["R1"] + zl + zc)
        result["rl"] = current * (zl + zc)
        result["lc"] = current * zc
    else:
        raise AssertionError("not a passive filter: " + case_id)
    return result


def finite_gain_opamp_voltages(case_id, values, gain):
    """Solve KCL with Vout = A(Vplus - Vminus), without exporter imports."""
    result = {"0": 0.0}
    if case_id == "opamp-inverting":
        vin = values["V1"]
        ratio = values["Rf"] / values["Rin"]
        out = -vin * ratio / (1 + (1 + ratio) / gain)
        result.update(vin=vin, out=out, sum=-out / gain)
    elif case_id == "opamp-noninverting":
        vin = values["V1"]
        ideal_gain = 1 + values["Rf"] / values["Rg"]
        out = vin * ideal_gain / (1 + ideal_gain / gain)
        result.update(vin=vin, out=out, sum=out / ideal_gain)
    elif case_id == "opamp-summer":
        weighted = values["Va"] * values["Rf"] / values["Ra"]
        weighted += values["Vb"] * values["Rf"] / values["Rb"]
        noise_gain = 1 + values["Rf"] / values["Ra"] + values["Rf"] / values["Rb"]
        out = -weighted / (1 + noise_gain / gain)
        result.update(va=values["Va"], vb=values["Vb"], out=out, sum=-out / gain)
    else:
        raise AssertionError("not an opamp case: " + case_id)
    return result


class IndependentGalleryOracleTests(unittest.TestCase):
    def assertClose(self, actual, expected, label=""):
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
                        "%s: %r != %r" % (label, actual, expected))

    def test_catalog_has_all_twelve_independently_specified_circuits(self):
        self.assertEqual({p.stem for p in CASE_DIR.glob("*.json")}, CASE_IDS)
        self.assertEqual(set(load_oracles()), CASE_IDS)

    def test_ordered_terminals_counts_values_and_source_polarities_match_oracle(self):
        for case_id, oracle in load_oracles().items():
            with self.subTest(case=case_id):
                spec = load_case(case_id)
                ec.validate_spec(spec)
                actual = {}
                for component in spec["components"]:
                    nets = [spec["nodes"][p]["net"] for p in component["pins"]]
                    if component["kind"] == "opamp":
                        # Oracle E1: out+, out-, control+, control-. The diagram's
                        # U1 convention is plus, minus, out, with ground implicit.
                        self.assertEqual(component["ref"], "U1")
                        actual["E1"] = ("E", component["gain"],
                                        [nets[2], "0", nets[0], nets[1]])
                    else:
                        actual[component["ref"]] = (component["kind"],
                                                     component["value"], nets)
                expected = {c["ref"]: (c["type"], c["value"], c["nodes"])
                            for c in oracle["components"]}
                self.assertEqual(actual, expected)
                self.assertEqual(len(actual), oracle["component_count"])
                self.assertEqual(Counter(c[0] for c in actual.values()), oracle["counts_by_type"])

    def test_every_node_dc_value_and_output_polarity_match_independent_oracle(self):
        for case_id, oracle in load_oracles().items():
            with self.subTest(case=case_id):
                spec = load_case(case_id)
                voltages = oracle["dc"]["node_voltages_V"]
                self.assertEqual({node["net"] for node in spec["nodes"].values()}, set(voltages))
                probes = spec["analysis"]["measurements"]
                self.assertEqual({m["positive"] for m in probes if m["negative"] == "0"},
                                 set(voltages) - {"0"})
                expected_output = re.fullmatch(r"V\(([^,]+),([^,]+)\)", oracle["measurement"])
                self.assertIsNotNone(expected_output)
                output = next(m for m in probes if m["name"] == "output")
                self.assertEqual((output["positive"], output["negative"]), expected_output.groups())
                targets = measured_values(spec, voltages)
                self.assertEqual(set(spec["expected"]["dc"]), set(targets))
                for name, value in targets.items():
                    self.assertClose(spec["expected"]["dc"][name], value, case_id + "/" + name)

    def test_filter_complex_outputs_and_frequency_points_match_oracle(self):
        for case_id, oracle in load_oracles().items():
            if "ac" not in oracle:
                continue
            spec = load_case(case_id)
            values = {c["ref"]: c["value"] for c in oracle["components"]}
            self.assertEqual(components_by_ref(spec)["V1"]["ac"], 1)
            self.assertEqual(spec["analysis"]["ac_hz"], [row["frequency_Hz"] for row in oracle["ac"]])
            for actual, expected in zip(spec["expected"]["ac"], oracle["ac"]):
                with self.subTest(case=case_id, frequency=expected["frequency_Hz"]):
                    self.assertEqual(actual["frequency"], expected["frequency_Hz"])
                    self.assertClose(actual["values"]["output"][0], expected["real"])
                    self.assertClose(actual["values"]["output"][1], expected["imag"])
                    nodes = filter_voltages(case_id, values, expected["frequency_Hz"])
                    # Also check internal-node expectations, including the RLC
                    # capacitor voltage, against independent impedance equations.
                    for name, voltage in measured_values(spec, nodes).items():
                        self.assertClose(actual["values"][name][0], voltage.real, name + " real")
                        self.assertClose(actual["values"][name][1], voltage.imag, name + " imag")

    def test_independent_oracle_branch_currents_obey_kirchhoff_current_law(self):
        for case_id, oracle in load_oracles().items():
            with self.subTest(case=case_id):
                current_balance = defaultdict(float)
                for component in oracle["components"]:
                    a, b = component["nodes"][:2]
                    current = oracle["dc"]["branch_currents_A"][component["ref"]]
                    current_balance[a] += current
                    current_balance[b] -= current
                for node, residual in current_balance.items():
                    self.assertAlmostEqual(residual, 0, delta=1e-12, msg=case_id + "/" + node)


@unittest.skipUnless(os.environ.get("CIRCUIT_RUN_SPICE") == "1",
                     "set CIRCUIT_RUN_SPICE=1 to require real ngspice")
class RealVerifiedCircuitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("ngspice") is None:
            raise RuntimeError("CIRCUIT_RUN_SPICE=1 requires ngspice on PATH")

    def run_checked(self, spec, directory):
        report = ec.simulate(spec, directory)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["errors"], [])
        for run in report["runs"]:
            self.assertEqual(run["status"], "pass")
            self.assertTrue(all(m["passed"] for m in run["measurements"].values()))
            for path in run["artifacts"].values():
                self.assertGreater((Path(directory) / path).stat().st_size, 0)
        return report

    def test_all_twelve_gallery_circuits_and_dc_branch_currents(self):
        analyses = 0
        with tempfile.TemporaryDirectory(prefix="verified-gallery-") as temporary:
            for case_id, oracle in load_oracles().items():
                with self.subTest(case=case_id):
                    directory = Path(temporary) / case_id
                    report = self.run_checked(load_case(case_id), directory)
                    analyses += len(report["runs"])
                    plot = ec.parse_raw((directory / "dc.raw").read_text(encoding="utf-8"))[0]
                    vectors = {name.casefold(): value for name, value in zip(plot.variables, plot.points[0])}
                    voltages = {"0": 0j}
                    for node in oracle["dc"]["node_voltages_V"]:
                        if node != "0":
                            voltages[node] = vectors["v(" + node + ")"]
                    for component in oracle["components"]:
                        ref, kind = component["ref"], component["type"]
                        target = oracle["dc"]["branch_currents_A"][ref]
                        if kind == "R":
                            a, b = component["nodes"]
                            actual = (voltages[a] - voltages[b]) / component["value"]
                        elif kind in ("V", "L", "E"):
                            vector_ref = "eu1" if kind == "E" else ref.casefold()
                            actual = vectors["i(" + vector_ref + ")"]
                        else:
                            # Ideal capacitors are open at DC; independent
                            # source currents are specified, not solved vectors.
                            continue
                        self.assertLessEqual(abs(actual - target), 1e-11 + 1e-6 * abs(target),
                                             case_id + "/" + ref)
        self.assertEqual(analyses, 24)

    def test_thirty_parameter_variations_against_analytic_equations(self):
        runs = 0
        with tempfile.TemporaryDirectory(prefix="verified-sweep-") as temporary:
            def check(spec):
                nonlocal runs
                report = self.run_checked(spec, Path(temporary) / ("case_%02d" % runs))
                self.assertEqual(len(report["runs"]), 1)
                runs += 1

            for case_id in ("divider-unloaded", "divider-loaded"):
                for top, bottom, load, source in (
                        (100, 1000, 10000, -3),
                        (1e6, 1000, 100, 5),
                        (1000, 1e6, 1e7, 0.25)):
                    with self.subTest(case=case_id, top=top, bottom=bottom, source=source):
                        spec = load_case(case_id)
                        parts = components_by_ref(spec)
                        parts["V1"]["value"] = source
                        parts["Rtop"]["value"] = top
                        parts["Rbottom"]["value"] = bottom
                        effective_bottom = bottom
                        if case_id == "divider-loaded":
                            parts["Rload"]["value"] = load
                            effective_bottom = 1 / (1 / bottom + 1 / load)
                        out = source * effective_bottom / (top + effective_bottom)
                        check(dc_only(spec, {"0": 0, "vcc": source, "out": out}))

            filters = (
                ("rc-lowpass", {"R1": 3300, "C1": 22e-9}, -0.7),
                ("rc-highpass", {"R1": 470, "C1": 2.2e-6}, 2.5),
                ("rl-lowpass", {"R1": 220, "L1": 47e-3}, 0.7),
                ("series-rlc", {"R1": 22, "L1": 47e-3, "C1": 220e-9}, 1.2),
            )
            for case_id, values, amplitude in filters:
                if case_id.startswith("rc-"):
                    characteristic = 1 / (2 * math.pi * values["R1"] * values["C1"])
                elif case_id == "rl-lowpass":
                    characteristic = values["R1"] / (2 * math.pi * values["L1"])
                else:
                    characteristic = 1 / (2 * math.pi * math.sqrt(values["L1"] * values["C1"]))
                for factor in (0.01, 1, 100):
                    with self.subTest(case=case_id, corner_multiple=factor):
                        spec = load_case(case_id)
                        parts = components_by_ref(spec)
                        for ref, value in values.items():
                            parts[ref]["value"] = value
                        parts["V1"]["ac"] = amplitude
                        frequency = factor * characteristic
                        nodes = filter_voltages(case_id, values, frequency, amplitude)
                        check(ac_only(spec, frequency, nodes))

            amplifiers = (
                ("opamp-inverting", {"Rin": 4700, "Rf": 33000, "V1": -0.03}),
                ("opamp-noninverting", {"Rg": 2200, "Rf": 47000, "V1": -0.12}),
                ("opamp-summer", {"Ra": 2200, "Rb": 4700, "Rf": 10000, "Va": -0.12, "Vb": 0.07}),
            )
            for case_id, values in amplifiers:
                for gain in (25, 1e3, 1e8):
                    with self.subTest(case=case_id, open_loop_gain=gain):
                        spec = load_case(case_id)
                        parts = components_by_ref(spec)
                        for ref, value in values.items():
                            parts[ref]["value"] = value
                        parts["U1"]["gain"] = gain
                        check(dc_only(spec, finite_gain_opamp_voltages(case_id, values, gain)))

            for r1, r2, current in ((470, 2200, -0.005), (1e6, 4.7e6, 1e-6), (10, 22, 0)):
                with self.subTest(case="parallel-current", r1=r1, r2=r2, current=current):
                    spec = load_case("parallel-current")
                    parts = components_by_ref(spec)
                    parts["R1"]["value"], parts["R2"]["value"] = r1, r2
                    parts["I1"]["value"] = current
                    check(dc_only(spec, {"0": 0, "out": current / (1 / r1 + 1 / r2)}))
        self.assertEqual(runs, 30)

    def test_structurally_valid_wrong_circuits_fail_expected_value_checks(self):
        mutations = []
        reversed_voltage = load_case("divider-unloaded")
        components_by_ref(reversed_voltage)["V1"]["pins"].reverse()
        mutations.append(("reversed_voltage_polarity", reversed_voltage))

        reversed_current = load_case("parallel-current")
        components_by_ref(reversed_current)["I1"]["pins"].reverse()
        mutations.append(("reversed_current_arrow", reversed_current))

        wrong_load = load_case("divider-loaded")
        components_by_ref(wrong_load)["Rload"]["value"] = 1000
        mutations.append(("wrong_load", wrong_load))

        wrong_probe = load_case("series-rlc")
        wrong_probe["analysis"]["dc"] = False
        wrong_probe["analysis"]["ac_hz"] = wrong_probe["analysis"]["ac_hz"][:1]
        wrong_probe["expected"]["dc"] = {}
        wrong_probe["expected"]["ac"] = wrong_probe["expected"]["ac"][:1]
        output = next(m for m in wrong_probe["analysis"]["measurements"] if m["name"] == "output")
        output["positive"], output["negative"] = output["negative"], output["positive"]
        mutations.append(("wrong_differential_probe_sign", wrong_probe))

        wrong_feedback = load_case("opamp-inverting")
        parts = components_by_ref(wrong_feedback)
        parts["U1"]["gain"] = 100
        values = {ref: part["value"] for ref, part in parts.items() if ref != "U1"}
        dc_only(wrong_feedback, finite_gain_opamp_voltages("opamp-inverting", values, 100))
        plus, minus, out = parts["U1"]["pins"]
        parts["U1"]["pins"] = [minus, plus, out]
        wrong_feedback["nodes"][minus]["anchor"] = "U1.plus"
        wrong_feedback["nodes"][plus]["anchor"] = "U1.minus"
        mutations.append(("wrong_opamp_control_sign", wrong_feedback))

        with tempfile.TemporaryDirectory(prefix="verified-mutations-") as temporary:
            for label, spec in mutations:
                with self.subTest(mutation=label):
                    ec.validate_spec(spec)
                    directory = Path(temporary) / label
                    with self.assertRaises(ec.SimulationError) as raised:
                        ec.simulate(spec, directory)
                    report = raised.exception.report
                    self.assertIsNotNone(report)
                    self.assertEqual(report["status"], "fail")
                    self.assertEqual(len(report["runs"]), 1)
                    self.assertTrue(any("voltage mismatch" in error for error in report["errors"]))
                    self.assertFalse(any("error" in run for run in report["runs"]),
                                     "must fail a value comparison, not simulator execution")
                    self.assertTrue((directory / "report.json").is_file())
        self.assertEqual(len(mutations), 5)


if __name__ == "__main__":
    unittest.main()
