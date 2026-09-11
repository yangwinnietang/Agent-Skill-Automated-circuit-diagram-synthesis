"""Validate resources that are essential to skill installation and image usage."""
import base64
from pathlib import Path
import re
import struct
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]


def png_chunks(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not PNG bytes')
    offset = 8
    while offset < len(data):
        length = struct.unpack('>I', data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        payload = data[offset+8:offset+8+length]
        crc = struct.unpack('>I', data[offset+8+length:offset+12+length])[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise ValueError('bad PNG checksum')
        yield kind, payload
        offset += 12 + length
        if kind == b'IEND':
            break


class ResourceTests(unittest.TestCase):
    def test_readme_image_is_real_decodable_png(self):
        chunks = list(png_chunks((ROOT / 'photo.png').read_bytes()))
        self.assertEqual(chunks[0][0], b'IHDR')
        self.assertEqual(chunks[-1][0], b'IEND')
        self.assertGreater(len(zlib.decompress(b''.join(p for k,p in chunks if k == b'IDAT'))), 1000)

    def test_original_corrupt_fixture_retained_as_text(self):
        data = (ROOT / 'tests/fixtures/original-photo.png.base64').read_bytes()
        raw = base64.b64decode(data)
        with self.assertRaises(ValueError):
            list(png_chunks(raw))

    def test_skill_local_links_resolve(self):
        for file in [ROOT / 'SKILL.md', *(ROOT / 'references').glob('*.md')]:
            for link in re.findall(r'\]\(([^)]+)\)', file.read_text()):
                if not link.startswith(('https://', 'http://', '#')):
                    self.assertTrue((file.parent / link).is_file(), f'{file.name}: {link}')

    def test_installed_skill_has_essential_resources(self):
        for file in ['SKILL.md', 'assets/template.tex', 'assets/template-zh.tex',
                     'scripts/compile_circuit.py', 'scripts/example.py', 'references/reference.md',
                     'references/image-reconstruction.md']:
            self.assertTrue((ROOT / file).is_file())


if __name__ == '__main__':
    unittest.main()
