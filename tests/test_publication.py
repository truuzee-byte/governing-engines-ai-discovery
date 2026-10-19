import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('publication', Path(__file__).resolve().parents[1] / 'tools/publication.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory(dir=p.ROOT)
        self.old = p.OUT
        p.OUT = Path(self.tmp.name) / 'dist'
        p.build('https://example.invalid/research')

    def tearDown(self):
        p.OUT = self.old
        self.tmp.cleanup()

    def test_complete_project_subpath(self):
        result = p.validate('https://example.invalid/research', report=False)
        self.assertEqual(result['documents'], 8)

    def test_missing_document_fails(self):
        (p.OUT / 'human-feedback/index.html').unlink()
        with self.assertRaises(AssertionError):
            p.validate('https://example.invalid/research', report=False)

    def test_broken_link_fails(self):
        f = p.OUT / 'index.html'
        f.write_text(f.read_text(encoding='utf-8').replace('human-feedback/index.html', 'missing/index.html'), encoding='utf-8')
        with self.assertRaisesRegex(AssertionError, 'Broken link'):
            p.validate('https://example.invalid/research', report=False)

    def test_message_drift_fails(self):
        f = p.OUT / 'human-feedback/index.html'
        f.write_text(f.read_text(encoding='utf-8').replace(p.inputs()[0]['message'], 'different message'), encoding='utf-8')
        with self.assertRaises(AssertionError):
            p.validate('https://example.invalid/research', report=False)

    def test_malformed_jsonld_fails(self):
        f = p.OUT / 'index.html'
        f.write_text(f.read_text(encoding='utf-8').replace('"@context":', 'BROKEN:'), encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):
            p.validate('https://example.invalid/research', report=False)

    def test_markdown_comment_loss_fails(self):
        f = p.OUT / 'markdown/human-feedback.md'
        f.write_text('# stripped comment\n', encoding='utf-8')
        with self.assertRaises(AssertionError):
            p.validate('https://example.invalid/research', report=False)

    def test_reproducible_build(self):
        before = (p.OUT / 'build.json').read_bytes()
        p.build('https://example.invalid/research')
        self.assertEqual(before, (p.OUT / 'build.json').read_bytes())

    def test_root_url(self):
        p.build('https://example.invalid')
        p.validate('https://example.invalid', report=False)


if __name__ == '__main__':
    unittest.main()
