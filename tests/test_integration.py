"""Real tools, opt-in locally; required (no dependency skips) in CI."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.compile_circuit import build, BuildError

RUN = os.environ.get('CIRCUIT_RUN_INTEGRATION') == '1'
ENGINES = os.environ.get('CIRCUIT_TEST_ENGINES', 'pdflatex').split(',')


@unittest.skipUnless(RUN, 'Set CIRCUIT_RUN_INTEGRATION=1 for real TeX/Poppler tests')
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def verify_outputs(self, result):
        for path in result.artifacts.values():
            self.assertGreater(path.stat().st_size, 100)
        svg = ET.parse(result.artifacts['svg']).getroot()
        self.assertTrue(any(e.tag.endswith('path') for e in svg.iter()), 'SVG contains no vector paths')
        self.assertFalse(any(e.tag.endswith('image') for e in svg.iter()), 'Expected vector schematic, not embedded bitmap')
        png = result.artifacts['png'].read_bytes()
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        width, height = struct.unpack('>II', png[16:24])
        self.assertGreater(width, 100)
        self.assertGreater(height, 50)
        self.assertNotIn('Missing character:', result.log.read_text(errors='replace'))
        self.assertNotIn('cannot open font map', result.log.read_text(errors='replace'))
        self.assertFalse(any('Overfull' in w for w in result.warnings), result.warnings)

    def test_all_examples_all_requested_engines(self):
        files = (sorted((ROOT / 'assets/examples').glob('*.tex'))
                 + sorted((ROOT / 'tests/forward').glob('*.tex'))
                 + [ROOT / 'assets/template.tex', ROOT / 'tests/fixtures/reference-network.tex'])
        self.assertGreaterEqual(len(files), 17)
        for engine in ENGINES:
            for source in files:
                with self.subTest(engine=engine, source=source.name):
                    result = build(source, output_dir=self.root / engine / source.stem,
                                   engine=engine, formats=('svg', 'png'))
                    self.verify_outputs(result)

    def test_filename_paths_and_relative_include(self):
        source_dir = self.root / 'folder with spaces 电路'
        source_dir.mkdir()
        source = source_dir / '电路 name $ [1].tex'
        source.write_text((ROOT / 'assets/template.tex').read_text().replace('\\begin{circuitikz}', '\\begin{circuitikz}\n\\input{label.tex}'))
        (source_dir / 'label.tex').write_text('\\node at (2,4) {Included};')
        result = build(source, output_dir=self.root / 'new nested' / '输出', formats=('svg', 'png'))
        self.verify_outputs(result)
        self.assertEqual(result.artifacts['pdf'].stem, source.stem)
        self.assertEqual(sorted(p.name for p in source_dir.iterdir()), sorted([source.name, 'label.tex']))

    def test_bare_filename_from_current_directory(self):
        source = self.root / 'local.tex'
        shutil.copyfile(ROOT / 'assets/template.tex', source)
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/compile_circuit.py'), 'local.tex', '--format', 'svg'], cwd=self.root, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(source.with_suffix('.svg').is_file())

    def test_invalid_tex_preserves_old_outputs_and_nonzero(self):
        source = self.root / 'bad.tex'
        source.write_text('\\documentclass{article}\n\\begin{document}\\undefinedcommand\\end{document}')
        source.with_suffix('.pdf').write_text('previous user PDF')
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/compile_circuit.py'), str(source)], capture_output=True, timeout=120)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(source.with_suffix('.pdf').read_text(), 'previous user PDF')
        self.assertIn('Undefined control sequence', (self.root / 'bad.compile.log').read_text())

    def test_real_tex_timeout(self):
        source = self.root / 'loop.tex'
        source.write_text('\\documentclass{article}\\begin{document}\\loop\\iftrue\\repeat\\end{document}')
        with self.assertRaisesRegex(BuildError, 'timed out'):
            build(source, timeout=1)
        self.assertFalse(source.with_suffix('.pdf').exists())

    def test_multipage_pdf_preserved_but_export_refused(self):
        source = self.root / 'pages.tex'
        source.write_text('\\documentclass{article}\\begin{document}Page one\\newpage Page two\\end{document}')
        result = build(source)
        original = result.artifacts['pdf'].read_bytes()
        with self.assertRaisesRegex(BuildError, 'exactly one PDF page'):
            build(source, formats=('svg', 'png'))
        self.assertEqual(result.artifacts['pdf'].read_bytes(), original)
        self.assertFalse(source.with_suffix('.png').exists())

    def test_parallel_builds_isolate_auxiliary_files(self):
        source = ROOT / 'assets/examples/divider.tex'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda n: build(source, output_dir=self.root / str(n), passes=1), range(2)))
        self.assertEqual(len({r.artifacts['pdf'] for r in results}), 2)
        self.assertTrue(all(r.artifacts['pdf'].is_file() for r in results))
        self.assertFalse((source.parent / 'divider.aux').exists())

    def test_american_resistor_variant(self):
        source = self.root / 'american.tex'
        source.write_text((ROOT / 'assets/examples/divider.tex').read_text().replace('european resistors', 'american resistors'))
        self.verify_outputs(build(source, formats=('svg', 'png')))

    def test_source_polarity_in_rendered_pdf(self):
        # Check the emitted glyph positions, not whether source contains 'invert'.
        # The template's contract is positive at the upper supply terminal.
        for engine in ENGINES:
            with self.subTest(engine=engine):
                result = build(ROOT / 'assets/template.tex', engine=engine,
                               output_dir=self.root / engine)
                bbox = subprocess.run(['pdftotext', '-bbox', str(result.artifacts['pdf']), '-'],
                                      capture_output=True, check=True).stdout
                words = [e for e in ET.fromstring(bbox).iter() if e.tag.endswith('word')]
                plus = [float(e.attrib['yMin']) for e in words if e.text == '+']
                minus = [float(e.attrib['yMin']) for e in words if e.text in ('-', '\u2212')]
                self.assertEqual(len(plus), 1)
                self.assertEqual(len(minus), 1)
                self.assertLess(plus[0], minus[0], 'Source positive terminal must be above negative')

    def test_real_missing_glyph_rejected(self):
        if 'xelatex' not in ENGINES:
            self.skipTest('Include xelatex in CIRCUIT_TEST_ENGINES for missing-glyph coverage')
        source = self.root / 'missing-glyph.tex'
        source.write_text('\\documentclass{article}\\begin{document}X\\char"10FFFF\\end{document}')
        with self.assertRaisesRegex(BuildError, 'Missing glyphs'):
            build(source, engine='xelatex')
        self.assertFalse(source.with_suffix('.pdf').exists())

    def test_shell_escape_disabled(self):
        source = self.root / 'shell.tex'
        source.write_text('\\documentclass{article}\\begin{document}\\immediate\\write18{touch ESCAPED}Safe\\end{document}')
        build(source)
        self.assertFalse((self.root / 'ESCAPED').exists())

    def test_toolchain_check(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/compile_circuit.py'), '--check', '--format', 'svg', '--format', 'png'], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Toolchain check passed', result.stdout)

    @unittest.skipUnless(os.environ.get('CIRCUIT_TEST_CHINESE') == '1', 'Set CIRCUIT_TEST_CHINESE=1 for ctex/Fandol coverage')
    def test_chinese_labels(self):
        result = build(ROOT / 'assets/template-zh.tex', engine='xelatex', output_dir=self.root, formats=('svg', 'png'))
        self.verify_outputs(result)
        text = subprocess.run(['pdftotext', str(result.artifacts['pdf']), '-'], capture_output=True, text=True, check=True).stdout
        self.assertIn('电源', text)
        self.assertIn('负载', text)


if __name__ == '__main__':
    unittest.main()
