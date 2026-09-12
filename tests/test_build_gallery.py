"""Gallery orchestration contracts; real rendering is exercised elsewhere."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_gallery as gallery


class GalleryBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gallery-builder-")
        self.addCleanup(self.temporary.cleanup)
        # Windows temp paths can contain an 8.3 alias (RUNNER~1), while the
        # builder resolves it to the long path. Use that same file identity so
        # the final-index I/O fault injection matches the intended destination.
        self.root = Path(self.temporary.name).resolve()
        self.repository = self.root / "repository"
        self.spec_dir = self.repository / "assets/verified-circuits"
        self.spec_dir.mkdir(parents=True)
        self.spec = json.loads((ROOT / "assets/verified-circuits/divider-unloaded.json").read_text(encoding="utf-8"))
        self.spec_path = self.spec_dir / "divider-unloaded.json"
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")
        self.report = json.loads((ROOT / "docs/gallery/divider-unloaded/divider-unloaded.simulation/report.json").read_text(encoding="utf-8"))
        self.target = self.root / "output"
        patcher = patch.object(gallery, "ROOT", self.repository)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_builder(self, target=None, overwrite=False):
        arguments = ["--output-dir", str(target or self.target)]
        if overwrite:
            arguments.append("--overwrite")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return gallery.main(arguments)

    def fake_synthesize(self, spec, folder, **kwargs):
        # Reuse an actual committed report. These tests exercise orchestration,
        # not the numerical engine or PDF converter, which have separate tests.
        simulation = folder / (spec["id"] + ".simulation")
        simulation.mkdir(parents=True, exist_ok=True)
        (simulation / "report.json").write_text(json.dumps(self.report), encoding="utf-8")

    @staticmethod
    def fake_overview(folder):
        (folder / "overview.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")

    def test_pass_is_published_only_after_preview_and_final_index(self):
        def inspect_preview(folder):
            running = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(running["status"], "running")
            self.assertFalse((folder / "README.md").exists())
            self.assertTrue((folder / "divider-unloaded/README.md").is_file())
            self.fake_overview(folder)

        with patch.object(gallery, "synthesize", side_effect=self.fake_synthesize), \
                patch.object(gallery, "overview", side_effect=inspect_preview):
            self.assertEqual(self.run_builder(), 0)
        summary = json.loads((self.target / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["status"], "pass")
        self.assertEqual((summary["case_count"], summary["analysis_count"], summary["measurement_count"]),
                         (1, 1, 3))
        self.assertTrue((self.target / "README.md").is_file())
        self.assertTrue((self.target / "overview.svg").is_file())

    def test_all_existing_metadata_requires_explicit_overwrite(self):
        names = ("summary.json", "README.md", "overview.svg", "divider-unloaded/README.md")
        for index, name in enumerate(names):
            with self.subTest(metadata=name):
                target = self.root / ("protected_%d" % index)
                existing = target / name
                existing.parent.mkdir(parents=True)
                existing.write_bytes(b"previous user content")
                with patch.object(gallery, "synthesize", side_effect=self.fake_synthesize) as synthesize, \
                        patch.object(gallery, "overview", side_effect=self.fake_overview):
                    self.assertEqual(self.run_builder(target), 1)
                    synthesize.assert_not_called()
                    self.assertEqual(existing.read_bytes(), b"previous user content")
                    self.assertEqual(self.run_builder(target, overwrite=True), 0)
                self.assertNotEqual(existing.read_bytes(), b"previous user content")

    def test_metadata_type_and_symlink_conflicts_fail_even_with_overwrite(self):
        names = ("summary.json", "README.md", "overview.svg", "divider-unloaded/README.md")
        for index, name in enumerate(names):
            with self.subTest(directory_instead_of_file=name):
                target = self.root / ("directory_%d" % index)
                existing = target / name
                existing.mkdir(parents=True)
                sentinel = existing / "preserve.txt"
                sentinel.write_bytes(b"preserve")
                with patch.object(gallery, "synthesize") as synthesize:
                    self.assertEqual(self.run_builder(target, overwrite=True), 1)
                    synthesize.assert_not_called()
                self.assertEqual(sentinel.read_bytes(), b"preserve")

        target = self.root / "case_file"
        target.mkdir()
        (target / "divider-unloaded").write_bytes(b"preserve directory conflict")
        with patch.object(gallery, "synthesize") as synthesize:
            self.assertEqual(self.run_builder(target, overwrite=True), 1)
            synthesize.assert_not_called()
        self.assertFalse((target / "summary.json").exists())

        # Creating unprivileged symlinks is portable on POSIX. Windows exercises
        # the same ordinary metadata and directory protection cases above.
        if os.name == "posix":
            for index, name in enumerate(names):
                with self.subTest(symlink_metadata=name):
                    target = self.root / ("symlink_%d" % index)
                    link = target / name
                    link.parent.mkdir(parents=True)
                    outside = self.root / ("outside_%d.txt" % index)
                    outside.write_bytes(b"outside content")
                    link.symlink_to(outside)
                    with patch.object(gallery, "synthesize") as synthesize:
                        self.assertEqual(self.run_builder(target, overwrite=True), 1)
                        synthesize.assert_not_called()
                    self.assertTrue(link.is_symlink())
                    self.assertEqual(outside.read_bytes(), b"outside content")
            target = self.root / "symlink_case"
            target.mkdir()
            outside = self.root / "outside_directory"
            outside.mkdir()
            (target / "divider-unloaded").symlink_to(outside, target_is_directory=True)
            with patch.object(gallery, "synthesize") as synthesize:
                self.assertEqual(self.run_builder(target, overwrite=True), 1)
                synthesize.assert_not_called()
            self.assertEqual(list(outside.iterdir()), [])

    def test_every_spec_is_validated_before_creating_any_destination(self):
        traversal = deepcopy(self.spec)
        traversal["id"] = "../outside"
        duplicate = deepcopy(self.spec)
        duplicate["id"] = self.spec["id"].upper()
        wrong_connection = deepcopy(self.spec)
        wrong_connection["id"] = "invalid-circuit"
        wrong_connection["components"][0]["pins"] = ["unknown", "unknown"]
        variants = (traversal, duplicate, wrong_connection, {"id": "incomplete"}, None)
        extra = self.spec_dir / "z-second.json"
        for index, invalid in enumerate(variants):
            with self.subTest(invalid_input=index):
                extra.write_text("{broken json" if invalid is None else json.dumps(invalid), encoding="utf-8")
                with patch.object(gallery, "synthesize") as synthesize:
                    self.assertEqual(self.run_builder(), 1)
                    synthesize.assert_not_called()
                self.assertFalse(self.target.exists())
                self.assertFalse((self.root / "outside").exists())

    def test_preview_and_index_failures_never_leave_a_pass_summary(self):
        for index, failure in enumerate((KeyError("viewBox"), ET.ParseError("malformed SVG"), OSError("preview write failed"))):
            with self.subTest(preview_failure=type(failure).__name__):
                target = self.root / ("failed_%d" % index)
                with patch.object(gallery, "synthesize", side_effect=self.fake_synthesize), \
                        patch.object(gallery, "overview", side_effect=failure):
                    self.assertEqual(self.run_builder(target), 1)
                summary = json.loads((target / "summary.json").read_text(encoding="utf-8"))
                self.assertEqual(summary["status"], "fail")
                self.assertIn(str(failure), summary["error"])
                self.assertFalse((target / "README.md").exists())

        original_write = Path.write_text

        def fail_final_index(path, *args, **kwargs):
            if path == self.target / "README.md":
                raise OSError("index write failed")
            return original_write(path, *args, **kwargs)

        with patch.object(gallery, "synthesize", side_effect=self.fake_synthesize), \
                patch.object(gallery, "overview", side_effect=self.fake_overview), \
                patch.object(Path, "write_text", fail_final_index):
            self.assertEqual(self.run_builder(), 1)
        summary = json.loads((self.target / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["status"], "fail")
        self.assertEqual(summary["error"], "index write failed")


if __name__ == "__main__":
    unittest.main()
