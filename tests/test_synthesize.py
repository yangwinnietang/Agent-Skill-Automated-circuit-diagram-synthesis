"""Publication regressions and opt-in checks against real TeX and ngspice."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import synthesize as synthesis
from scripts.compile_circuit import BuildError
from scripts.electrical import SimulationError, load_spec


def divider():
    """Independent 10 V, 1 kohm + 1 kohm divider; output must be 5 V."""
    return {
        'id': 'tiny-divider', 'title': 'Independent divider',
        'nodes': {'top': {'net': 'vin', 'at': [0, 3]},
                  'tap': {'net': 'out', 'at': [4, 3]},
                  'return': {'net': '0', 'at': [0, 0]}},
        'components': [
            {'ref': 'V1', 'kind': 'V', 'pins': ['top', 'return'], 'value': 10},
            {'ref': 'R1', 'kind': 'R', 'pins': ['top', 'tap'], 'value': 1000},
            {'ref': 'R2', 'kind': 'R', 'pins': ['tap', 'return'], 'value': 1000}],
        'wires': [], 'grounds': ['return'], 'junctions': [],
        'ports': [{'point': 'tap', 'label': 'Output'}],
        'analysis': {'dc': True, 'ac_hz': [],
                     'measurements': [{'name': 'output', 'positive': 'out', 'negative': '0'}]},
        'expected': {'dc': {'output': 5}, 'ac': []},
    }


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'outputs'
        self.spec = divider()

    def save_old(self, suffix, contents='previous user artifact'):
        self.target.mkdir(exist_ok=True)
        path = self.target / (self.spec['id'] + suffix)
        path.parent.mkdir(exist_ok=True)
        path.write_text(contents, encoding='utf-8')
        return path

    def test_source_only_produces_editable_source_and_auditable_netlist(self):
        with patch.object(synthesis, 'build') as compile_tool, patch.object(synthesis, 'simulate') as simulate:
            paths = synthesis.synthesize(self.spec, self.target)
        self.assertEqual({p.suffix for p in paths}, {'.tex', '.cir', '.md'})
        tex = (self.target / 'tiny-divider.tex').read_text(encoding='utf-8')
        netlist = (self.target / 'tiny-divider.cir').read_text(encoding='utf-8')
        self.assertIn('\\end{document}', tex)
        self.assertIn('V1 vin 0 DC 10 AC 0', netlist)
        self.assertIn('R1 vin out 1000', netlist)
        self.assertIn('R2 out 0 1000', netlist)
        compile_tool.assert_not_called()
        simulate.assert_not_called()

    def test_any_existing_generated_file_requires_explicit_overwrite(self):
        for suffix in ('.tex', '.cir', '.connections.md', '.pdf', '.svg', '.png', '.compile.log',
                       '.simulation/report.json'):
            with self.subTest(suffix=suffix):
                path = self.save_old(suffix)
                with self.assertRaisesRegex(BuildError, 'Refusing to overwrite'), \
                        patch.object(synthesis, 'build') as compile_tool:
                    synthesis.synthesize(self.spec, self.target, formats=('pdf',))
                self.assertEqual(path.read_text(encoding='utf-8'), 'previous user artifact')
                compile_tool.assert_not_called()
                path.unlink()

    def test_compilation_failure_keeps_previous_outputs_and_new_source_diagnostics(self):
        old_tex = self.save_old('.tex', 'manually edited source')
        old_svg = self.save_old('.svg', 'old image')
        old_report = self.save_old('.simulation/report.json', 'old passing report')

        def fail_compile(tex, **options):
            tex.with_suffix('.compile.log').write_text('realistic compiler failure detail', encoding='utf-8')
            raise BuildError('compiler failed')

        with patch.object(synthesis, 'build', side_effect=fail_compile), \
                self.assertRaisesRegex(BuildError, 'Failure evidence:'):
            synthesis.synthesize(self.spec, self.target, formats=('svg',), overwrite=True)
        self.assertEqual(old_tex.read_text(), 'manually edited source')
        self.assertEqual(old_svg.read_text(), 'old image')
        self.assertEqual(old_report.read_text(), 'old passing report')
        failed = list(self.target.glob('failed-*'))
        self.assertEqual(len(failed), 1)
        self.assertIn('\\end{document}', (failed[0] / old_tex.name).read_text())
        self.assertIn('compiler failure detail', (failed[0] / 'tiny-divider.compile.log').read_text())

    def test_verification_failure_does_not_publish_new_images(self):
        old_tex = self.save_old('.tex', 'old source')
        old_pdf = self.save_old('.pdf', 'old PDF')
        old_report = self.save_old('.simulation/report.json', 'old report')

        def compile_success(tex, **options):
            tex.with_suffix('.pdf').write_text('new PDF')

        def fail_simulation(spec, output, **options):
            output.mkdir()
            (output / 'report.json').write_text('{"status":"fail"}')
            raise SimulationError('voltage mismatch')

        with patch.object(synthesis, 'build', side_effect=compile_success), \
                patch.object(synthesis, 'simulate', side_effect=fail_simulation), \
                self.assertRaisesRegex(BuildError, 'voltage mismatch'):
            synthesis.synthesize(self.spec, self.target, formats=('pdf',), verify=True, overwrite=True)
        self.assertEqual(old_tex.read_text(), 'old source')
        self.assertEqual(old_pdf.read_text(), 'old PDF')
        self.assertEqual(old_report.read_text(), 'old report')
        failed_report = next(self.target.glob('failed-*/tiny-divider.simulation/report.json'))
        self.assertEqual(json.loads(failed_report.read_text())['status'], 'fail')

    def test_source_only_overwrite_removes_stale_images_and_verification(self):
        stale = [self.save_old(suffix) for suffix in
                 ('.pdf', '.svg', '.png', '.compile.log', '.simulation/report.json',
                  '.simulation/dc.cir', '.simulation/dc.raw', '.simulation/dc.log',
                  '.simulation/ac_003.raw')]
        note = self.save_old('.simulation/my-notes.txt', 'keep notes')
        other = self.target / 'another.pdf'
        other.write_text('other case')
        synthesis.synthesize(self.spec, self.target, overwrite=True)
        self.assertTrue(all(not path.exists() for path in stale))
        self.assertEqual(note.read_text(), 'keep notes')
        self.assertEqual(other.read_text(), 'other case')

    def test_subset_format_overwrite_removes_unrequested_images(self):
        old_png = self.save_old('.png')
        old_svg = self.save_old('.svg')

        def compile_success(tex, **options):
            tex.with_suffix('.pdf').write_bytes(b'%PDF-1.5\nnew')
            tex.with_suffix('.compile.log').write_text('new compiler output')

        with patch.object(synthesis, 'build', side_effect=compile_success):
            published = synthesis.synthesize(self.spec, self.target, formats=('pdf',), overwrite=True)
        self.assertFalse(old_png.exists())
        self.assertFalse(old_svg.exists())
        self.assertIn(self.target / 'tiny-divider.pdf', published)

    def test_simulation_reports_are_separate_for_each_case(self):
        def simulate(spec, output, **options):
            output.mkdir()
            (output / 'report.json').write_text(json.dumps({'case_id': spec['id'], 'status': 'pass'}))

        with patch.object(synthesis, 'simulate', side_effect=simulate):
            synthesis.synthesize(self.spec, self.target, verify=True)
            second = copy.deepcopy(self.spec)
            second['id'] = 'second-divider'
            synthesis.synthesize(second, self.target, verify=True)
        for case_id in ('tiny-divider', 'second-divider'):
            report = self.target / (case_id + '.simulation') / 'report.json'
            self.assertEqual(json.loads(report.read_text())['case_id'], case_id)

    def test_file_created_during_compilation_is_not_overwritten(self):
        def create_user_file(tex, **options):
            self.save_old('.tex', 'user wrote this while compilation ran')
        with patch.object(synthesis, 'build', side_effect=create_user_file), \
                self.assertRaisesRegex(BuildError, 'Refusing to overwrite'):
            synthesis.synthesize(self.spec, self.target, formats=('pdf',))
        self.assertEqual((self.target / 'tiny-divider.tex').read_text(),
                         'user wrote this while compilation ran')

    def test_invalid_options_fail_before_creating_output_directory(self):
        for options in ({'timeout': 0}, {'timeout': float('nan')}, {'timeout': float('inf')},
                        {'timeout': True}, {'timeout': 10 ** 400}, {'engine': 'bad'},
                        {'formats': ('gif',)}, {'chinese': True}):
            with self.subTest(options=options), self.assertRaises(BuildError):
                synthesis.synthesize(self.spec, self.target, **options)
            self.assertFalse(self.target.exists())

    def test_directory_in_place_of_generated_file_is_rejected(self):
        (self.target / 'tiny-divider.pdf').mkdir(parents=True)
        with self.assertRaisesRegex(BuildError, 'Expected a file output'):
            synthesis.synthesize(self.spec, self.target, overwrite=True)
        self.assertFalse((self.target / 'tiny-divider.tex').exists())

    @unittest.skipUnless(os.name == 'posix', 'Uses a POSIX symlink')
    def test_symlink_generated_paths_cannot_redirect_or_replace_user_files(self):
        self.target.mkdir()
        outside = self.root / 'elsewhere'
        outside.mkdir()
        for suffix, destination in (('.tex', outside / 'missing.tex'),
                                    ('.simulation', outside)):
            with self.subTest(suffix=suffix):
                link = self.target / ('tiny-divider' + suffix)
                link.symlink_to(destination)
                with self.assertRaisesRegex(BuildError, 'symlink'):
                    synthesis.synthesize(self.spec, self.target, overwrite=True)
                self.assertTrue(link.is_symlink())
                self.assertEqual(list(outside.iterdir()), [])
                link.unlink()


class CliTests(unittest.TestCase):
    def test_module_invocation_from_repository_root(self):
        result = subprocess.run([sys.executable, '-m', 'scripts.synthesize', '--help'],
                                cwd=ROOT, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = root / 'spec.json'
            spec.write_text(json.dumps(divider()).replace('"id":', '"id": "ambiguous", "id":', 1))
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/synthesize.py'), str(spec),
                                     '--output-dir', str(root / 'out')], capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn(b'duplicate', result.stderr)
            self.assertNotIn(b'Traceback', result.stderr)
            self.assertFalse((root / 'out').exists())

    def test_unicode_source_output_on_ascii_console_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = root / 'spec.json'
            spec.write_text(json.dumps(divider()))
            output = root / '\u7535\u8def'
            args = [sys.executable, str(ROOT / 'scripts/synthesize.py'), str(spec), '--output-dir', str(output)]
            env = {**os.environ, 'PYTHONIOENCODING': 'ascii:strict'}
            first = subprocess.run(args, capture_output=True, env=env)
            self.assertEqual(first.returncode, 0, first.stderr.decode('ascii'))
            self.assertIn(b'\\u7535\\u8def', first.stdout)
            (output / 'tiny-divider.tex').write_text('user edit')
            second = subprocess.run(args, capture_output=True, env=env)
            self.assertEqual(second.returncode, 1)
            self.assertNotIn(b'Traceback', second.stderr)
            self.assertEqual((output / 'tiny-divider.tex').read_text(), 'user edit')


@unittest.skipUnless(os.environ.get('CIRCUIT_RUN_INTEGRATION') == '1', 'Requires real TeX/Poppler/ngspice')
class RealSynthesisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_divider_positive_terminal_is_above_negative_and_measures_five_volts(self):
        synthesis.synthesize(divider(), self.root, formats=('pdf',), verify=True)
        report = json.loads((self.root / 'tiny-divider.simulation/report.json').read_text())
        self.assertEqual(report['status'], 'pass')
        self.assertAlmostEqual(report['runs'][0]['measurements']['output']['actual'], 5, places=8)
        result = subprocess.run(['pdftotext', '-bbox', str(self.root / 'tiny-divider.pdf'), '-'],
                                capture_output=True, check=True)
        words = [word for word in ET.fromstring(result.stdout).iter() if word.tag.endswith('word')]
        plus = [float(w.attrib['yMin']) for w in words if w.text == '+']
        minus = [float(w.attrib['yMin']) for w in words if w.text in ('-', '\u2212')]
        self.assertEqual(len(plus), 1)
        self.assertEqual(len(minus), 1)
        self.assertLess(plus[0], minus[0])

    def test_special_characters_are_rendered_as_literal_label_text(self):
        spec = divider()
        spec['ports'][0]['label'] = r'\end{document}%_#$&^~SAFEEND'
        synthesis.synthesize(spec, self.root, formats=('pdf',))
        result = subprocess.run(['pdftotext', str(self.root / 'tiny-divider.pdf'), '-'],
                                capture_output=True, check=True, text=True)
        self.assertIn('SAFEEND', result.stdout)
        self.assertIn('end{document}', result.stdout)

    def test_real_compile_and_verification_failures_preserve_previous_success(self):
        spec = divider()
        paths = synthesis.synthesize(spec, self.root, formats=('pdf',), verify=True)
        previous = {path: path.read_bytes() for path in paths}
        invalid_label = copy.deepcopy(spec)
        invalid_label['ports'][0]['label'] = '\u7535\u8def'
        with self.assertRaisesRegex(BuildError, 'Failure evidence:'):
            synthesis.synthesize(invalid_label, self.root, formats=('pdf',), overwrite=True)
        for path, contents in previous.items():
            self.assertEqual(path.read_bytes(), contents)
        incorrect_voltage = copy.deepcopy(spec)
        incorrect_voltage['expected']['dc']['output'] = 6
        with self.assertRaisesRegex(BuildError, 'voltage mismatch'):
            synthesis.synthesize(incorrect_voltage, self.root, formats=('pdf',),
                                 verify=True, overwrite=True)
        for path, contents in previous.items():
            self.assertEqual(path.read_bytes(), contents)
        reports = list(self.root.glob('failed-*/tiny-divider.simulation/report.json'))
        self.assertEqual(len(reports), 1)
        self.assertEqual(json.loads(reports[0].read_text())['status'], 'fail')

    def test_opamp_anchors_and_point_names_do_not_collide_with_device_references(self):
        spec = load_spec(ROOT / 'assets/verified-circuits/opamp-inverting.json')
        renamed = {'UP': 'U_A', 'UM': 'DU_A', 'UO': 'PU_A'}
        spec['nodes'] = {renamed.get(name, name): node for name, node in spec['nodes'].items()}
        for node in spec['nodes'].values():
            if 'anchor' in node:
                node['anchor'] = node['anchor'].replace('U1.', 'u_a.')
        for component in spec['components']:
            component['pins'] = [renamed.get(pin, pin) for pin in component['pins']]
            if component['kind'] == 'opamp':
                component['ref'] = 'U_A'
            if component['ref'] == 'Rin':
                component['ref'] = 'R_in'
        spec['wires'] = [[renamed.get(pin, pin) for pin in wire] for wire in spec['wires']]
        synthesis.synthesize(spec, self.root, formats=('svg',), verify=True)
        report = json.loads((self.root / 'opamp-inverting.simulation/report.json').read_text())
        self.assertEqual(report['status'], 'pass')
        self.assertAlmostEqual(report['runs'][0]['measurements']['output']['actual'],
                               -0.9999890001209987, places=8)
        self.assertGreater((self.root / 'opamp-inverting.svg').stat().st_size, 100)

    def test_all_twelve_specs_compile_to_vectors_and_verify(self):
        files = sorted((ROOT / 'assets/verified-circuits').glob('*.json'))
        self.assertEqual(len(files), 12)
        for path in files:
            with self.subTest(case=path.stem):
                target = self.root / path.stem
                synthesis.synthesize(load_spec(path), target, formats=('svg',), verify=True)
                self.assertGreater((target / (path.stem + '.pdf')).stat().st_size, 100)
                svg = ET.parse(target / (path.stem + '.svg')).getroot()
                self.assertTrue(any(element.tag.endswith('path') for element in svg.iter()))
                self.assertFalse(any(element.tag.endswith('image') for element in svg.iter()))
                report = json.loads((target / (path.stem + '.simulation/report.json')).read_text())
                self.assertEqual(report['status'], 'pass')


if __name__ == '__main__':
    unittest.main()
