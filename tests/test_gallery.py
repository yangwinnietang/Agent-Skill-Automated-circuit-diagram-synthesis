"""Keep published diagrams and evidence tied to the current source specifications."""
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from electrical import load_spec, parse_raw, spice_netlist
from synthesize import render_tex
from test_resources import png_chunks


class PublishedGalleryTests(unittest.TestCase):
    def test_visual_review_identifies_current_images(self):
        record = json.loads((ROOT / "docs/validation/visual-review.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "pass")
        self.assertEqual(len(record["images"]), 12)
        for entry in record["images"]:
            with self.subTest(circuit=entry["circuit"]):
                self.assertEqual(entry["status"], "pass")
                self.assertEqual(hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest(), entry["sha256"])

    def test_published_sources_and_reports_match_current_specs(self):
        specs = sorted((ROOT / "assets/verified-circuits").glob("*.json"))
        summary = json.loads((ROOT / "docs/gallery/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(len(specs), 12)
        self.assertEqual(summary["status"], "pass")
        self.assertEqual({c["id"] for c in summary["cases"]}, {p.stem for p in specs})
        analyses = measurements = 0
        for path in specs:
            with self.subTest(circuit=path.stem):
                spec = load_spec(path)
                folder = ROOT / "docs/gallery" / spec["id"]
                self.assertEqual((folder / f"{spec['id']}.tex").read_text(encoding="utf-8"), render_tex(spec))
                report = json.loads((folder / f"{spec['id']}.simulation/report.json").read_text(encoding="utf-8"))
                digest = hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
                self.assertEqual(report["spec_sha256"], digest)
                self.assertEqual(report["status"], "pass")
                self.assertFalse(report["errors"])
                for run in report["runs"]:
                    sim = folder / f"{spec['id']}.simulation"
                    analysis = "dc" if run["analysis"] == "dc" else run["frequency_hz"]
                    self.assertEqual((sim / run["artifacts"]["netlist"]).read_text(encoding="utf-8"), spice_netlist(spec, analysis))
                    self.assertTrue(parse_raw((sim / run["artifacts"]["raw"]).read_text(encoding="utf-8")))
                    self.assertTrue((sim / run["artifacts"]["log"]).is_file())
                    self.assertTrue(all(m["passed"] for m in run["measurements"].values()))
                    analyses += 1
                    measurements += len(run["measurements"])
        self.assertEqual((analyses, measurements), (24, 81))
        self.assertEqual((summary["analysis_count"], summary["measurement_count"]), (analyses, measurements))

    def test_all_twelve_have_valid_three_format_exports(self):
        for path in (ROOT / "assets/verified-circuits").glob("*.json"):
            folder = ROOT / "docs/gallery" / path.stem
            with self.subTest(circuit=path.stem):
                self.assertTrue((folder / (path.stem + ".pdf")).read_bytes().startswith(b"%PDF-"))
                root = ET.parse(folder / (path.stem + ".svg")).getroot()
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertEqual(list(png_chunks((folder / (path.stem + ".png")).read_bytes()))[-1][0], b"IEND")

    def test_documentation_local_links_resolve(self):
        documents = [ROOT / "README.md", ROOT / "TESTING.md", ROOT / "SKILL.md",
                     *(ROOT / "references").glob("*.md"), *(ROOT / "docs").rglob("*.md")]
        for document in documents:
            for link in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                if link.startswith(("https://", "http://", "#")):
                    continue
                with self.subTest(document=str(document.relative_to(ROOT)), link=link):
                    self.assertTrue((document.parent / link.split("#", 1)[0]).exists())


if __name__ == "__main__":
    unittest.main()
