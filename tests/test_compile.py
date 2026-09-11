import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import compile_circuit as cc
from scripts import example


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'diagram.tex'
        self.source.write_text('source remains editable')
        self.output = self.root / 'output'
        self.calls = []
        self.mode = ''
        self.which = patch.object(cc.shutil, 'which', side_effect=lambda name: '/tools/' + name)
        self.which.start()
        self.addCleanup(self.which.stop)
        self.run = patch.object(cc, '_run', side_effect=self.fake_run)
        self.run.start()
        self.addCleanup(self.run.stop)

    def fake_run(self, command, cwd, log, timeout):
        self.calls.append((command, cwd))
        tool = Path(command[0]).name
        if tool in ('pdflatex', 'xelatex', 'lualatex'):
            if self.mode == 'compile-fail':
                log.write(b'Unknown control sequence at line 8\n')
                raise cc.BuildError('compiler failed')
            work = Path(next(x.split('=', 1)[1] for x in command if x.startswith('-output-directory=')))
            if self.mode != 'no-pdf':
                (work / 'circuit.pdf').write_bytes(b'garbage' if self.mode == 'bad-pdf' else b'%PDF-1.5\ncontent')
            if self.mode == 'missing-glyph':
                log.write(b'Missing character: There is no U+4E2D in font\n')
            if self.mode == 'warning':
                log.write(b'LaTeX Warning: unresolved reference\n')
        elif tool == 'pdfinfo':
            log.write(b'Pages: 2\n' if self.mode == 'multipage' else b'Pages: 1\n')
        else:
            if self.mode == 'convert-fail':
                log.write(b'conversion failed\n')
                raise cc.BuildError('converter failed')
            if self.mode == 'no-export':
                return
            if '-png' in command:
                Path(command[-1] + '.png').write_bytes(b'\x89PNG\r\n\x1a\nbytes')
            else:
                target = Path(command[-2] if tool == 'pdf2svg' else command[-1])
                target.write_text('<broken' if self.mode == 'bad-svg' else '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L1 1"/></svg>')

    def build(self, **kwargs):
        return cc.build(self.source, output_dir=self.output, **kwargs)

    def test_default_pdf_and_source_untouched(self):
        result = self.build()
        self.assertEqual(set(result.artifacts), {'pdf'})
        self.assertEqual(result.artifacts['pdf'].read_bytes(), b'%PDF-1.5\ncontent')
        self.assertEqual(self.source.read_text(), 'source remains editable')
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(result.log.exists())

    def test_all_formats(self):
        result = self.build(formats=('svg', 'png'))
        self.assertEqual(set(result.artifacts), {'pdf', 'svg', 'png'})
        for path in result.artifacts.values():
            self.assertTrue(path.is_file())

    def test_formats_string_and_duplicates(self):
        self.assertIn('svg', self.build(formats='svg').artifacts)
        self.calls.clear()
        self.build(formats=('svg', 'svg', 'pdf'))
        self.assertEqual(sum(Path(x[0][0]).name == 'pdftocairo' for x in self.calls), 1)

    def test_missing_input(self):
        self.source.unlink()
        with self.assertRaisesRegex(cc.BuildError, 'existing .tex'):
            self.build()
        self.assertFalse(self.calls)

    def test_directory_is_not_input(self):
        self.source.unlink()
        self.source.mkdir()
        with self.assertRaises(cc.BuildError):
            self.build()

    def test_wrong_extension(self):
        target = self.root / 'diagram.txt'
        target.write_text('text')
        with self.assertRaisesRegex(cc.BuildError, '.tex'):
            cc.build(target)

    def test_missing_engine(self):
        with patch.object(cc.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(cc.BuildError, 'pdflatex'):
                self.build()

    def test_missing_svg_tools(self):
        with patch.object(cc.shutil, 'which', side_effect=lambda x: '/tools/pdflatex' if x == 'pdflatex' else None):
            with self.assertRaisesRegex(cc.BuildError, 'SVG requires'):
                self.build(formats=('svg',))

    def test_missing_pdfinfo(self):
        with patch.object(cc.shutil, 'which', side_effect=lambda x: None if x == 'pdfinfo' else '/tools/' + x):
            with self.assertRaisesRegex(cc.BuildError, 'pdfinfo'):
                self.build(formats=('png',))

    def test_pdf2svg_fallback(self):
        with patch.object(cc.shutil, 'which', side_effect=lambda x: None if x == 'pdftocairo' else '/tools/' + x):
            self.assertIn('svg', self.build(formats=('svg',)).artifacts)
            self.assertEqual(Path(self.calls[-1][0][0]).name, 'pdf2svg')

    def test_png_requires_pdftocairo(self):
        with patch.object(cc.shutil, 'which', side_effect=lambda x: None if x == 'pdftocairo' else '/tools/' + x):
            with self.assertRaisesRegex(cc.BuildError, 'pdftocairo'):
                self.build(formats=('png',))

    def test_invalid_parameters_before_execution(self):
        for kwargs in ({'engine': 'shell'}, {'formats': ['gif']}, {'timeout': 0}, {'timeout': -1},
                       {'timeout': float('nan')}, {'timeout': float('inf')}, {'passes': 0},
                       {'passes': 4}, {'passes': 1.5}, {'dpi': 0}, {'dpi': 1201}):
            with self.subTest(kwargs=kwargs), self.assertRaises(cc.BuildError):
                self.build(**kwargs)
        self.assertFalse(self.calls)

    def test_compile_failure_logs_and_preserves_old_output(self):
        self.output.mkdir()
        old = self.output / 'diagram.pdf'
        old.write_bytes(b'old PDF')
        self.mode = 'compile-fail'
        with self.assertRaisesRegex(cc.BuildError, 'Build log'):
            self.build()
        self.assertEqual(old.read_bytes(), b'old PDF')
        self.assertIn('line 8', (self.output / 'diagram.compile.log').read_text())

    def test_converter_failure_publishes_nothing(self):
        self.output.mkdir()
        for ext in ['pdf', 'svg', 'png']:
            (self.output / ('diagram.' + ext)).write_text('old')
        self.mode = 'convert-fail'
        with self.assertRaises(cc.BuildError):
            self.build(formats=('svg', 'png'))
        for ext in ['pdf', 'svg', 'png']:
            self.assertEqual((self.output / ('diagram.' + ext)).read_text(), 'old')

    def test_success_without_pdf_rejected(self):
        self.mode = 'no-pdf'
        with self.assertRaisesRegex(cc.BuildError, 'no nonempty PDF'):
            self.build()

    def test_invalid_pdf_rejected(self):
        self.mode = 'bad-pdf'
        with self.assertRaisesRegex(cc.BuildError, 'not a PDF'):
            self.build()

    def test_success_without_export_rejected(self):
        self.mode = 'no-export'
        with self.assertRaisesRegex(cc.BuildError, 'no nonempty SVG'):
            self.build(formats=('svg',))
        self.assertFalse((self.output / 'diagram.pdf').exists())

    def test_invalid_svg_rejected(self):
        self.mode = 'bad-svg'
        with self.assertRaisesRegex(cc.BuildError, 'malformed SVG'):
            self.build(formats=('svg',))

    def test_missing_glyph_is_failure(self):
        self.mode = 'missing-glyph'
        with self.assertRaisesRegex(cc.BuildError, 'Missing glyphs'):
            self.build()

    def test_warnings_returned_once(self):
        self.mode = 'warning'
        self.assertEqual(self.build().warnings, ['LaTeX Warning: unresolved reference'])

    def test_multipage_export_rejected(self):
        self.mode = 'multipage'
        with self.assertRaisesRegex(cc.BuildError, 'exactly one PDF page'):
            self.build(formats=('svg',))
        self.assertFalse((self.output / 'diagram.pdf').exists())

    def test_safe_invocation_and_source_cwd(self):
        self.build(passes=1)
        command, cwd = self.calls[0]
        self.assertEqual(cwd, self.source.parent)
        self.assertIn('-no-shell-escape', command)
        self.assertIn('-halt-on-error', command)
        self.assertIn('-interaction=nonstopmode', command)
        self.assertEqual(Path(command[-1]).name, 'circuit.tex')
        self.assertFalse(Path(command[-1]).parent.exists())

    def test_output_directory_is_file(self):
        self.output.write_text('keep me')
        with self.assertRaisesRegex(cc.BuildError, 'File operation failed'):
            self.build()
        self.assertEqual(self.output.read_text(), 'keep me')

    def test_boolean_compatibility_helper(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertTrue(cc.compile_circuit(self.source))
            self.mode = 'compile-fail'
            self.assertFalse(cc.compile_circuit(self.source))

    def test_cli_returns_failure(self):
        self.mode = 'compile-fail'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cc.main([str(self.source)]), 1)

    def test_check_prints_log_before_cleanup(self):
        self.mode = 'compile-fail'
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(cc.main(['--check']), 1)
        self.assertIn('line 8', stderr.getvalue())

    def test_invalid_artifact_signatures(self):
        for kind, contents in [('png', b'bad'), ('svg', b'<html/>'), ('pdf', b'')]:
            with self.subTest(kind=kind):
                file = self.root / ('artifact.' + kind)
                file.write_bytes(contents)
                with self.assertRaises(cc.BuildError):
                    cc._validate_artifact(file, kind)

    def test_publish_failure_preserves_destination(self):
        target = self.root / 'old.pdf'
        target.write_text('old')
        with patch.object(cc.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                cc._publish(self.source, target)
        self.assertEqual(target.read_text(), 'old')
        self.assertFalse(list(self.root.glob('.publish-*')))


class ProcessTests(unittest.TestCase):
    def test_timeout_really_terminates_process(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryFile() as log:
            start = time.monotonic()
            with self.assertRaisesRegex(cc.BuildError, 'timed out'):
                cc._run([sys.executable, '-c', 'import time; time.sleep(30)'], temp, log, .1)
            self.assertLess(time.monotonic() - start, 5)

    def test_nonzero_process_and_logs(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryFile() as log:
            with self.assertRaisesRegex(cc.BuildError, 'exit 7'):
                cc._run([sys.executable, '-c', 'print("diagnostic",flush=True); raise SystemExit(7)'], temp, log, 5)
            log.seek(0)
            self.assertIn(b'diagnostic', log.read())

    def test_missing_executable(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryFile() as log:
            with self.assertRaisesRegex(cc.BuildError, 'Could not run'):
                cc._run([str(Path(temp) / 'absent')], temp, log, 5)

    def test_cli_missing_file_nonzero_in_actual_process(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/compile_circuit.py'), 'no-such-file.tex'], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(b'Traceback', result.stderr)

    def test_cli_invalid_usage(self):
        for args in [[], ['--check', 'file.tex'], ['--engine', 'bad']]:
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/compile_circuit.py'), *args], capture_output=True)
                self.assertEqual(result.returncode, 2)


class ExampleTests(unittest.TestCase):
    def test_list(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(example.main(['--list']), 0)
        self.assertIn('wheatstone', output.getvalue())

    def test_copy_and_protect_existing_edits(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            args = ['--name', 'divider', '--output-dir', temp]
            self.assertEqual(example.main(args), 0)
            target = Path(temp) / 'divider.tex'
            self.assertIn('\\end{document}', target.read_text())
            target.write_text('user edits')
            self.assertEqual(example.main(args), 1)
            self.assertEqual(target.read_text(), 'user edits')

    def test_copy_from_unrelated_cwd(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/example.py'), '--name', 'logic-and', '--output-dir', temp], cwd=temp, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertTrue((Path(temp) / 'logic-and.tex').exists())

    def test_compile_failure_propagates(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(example, 'compile_circuit', return_value=False), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(example.main(['--output-dir', temp, '--compile']), 1)

    def test_reject_format_without_compile(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            example.main(['--output-dir', 'unused', '--format', 'svg'])
        self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
