import json
import unittest
import test_publication as original
from ingest_corpus import scrub
p = original.p


class CorpusTests(unittest.TestCase):
    setUp = original.PublicationTests.setUp
    tearDown = original.PublicationTests.tearDown

    def test_corpus_inventory_and_graph(self):
        result = p.validate('https://example.invalid/research', report=False)
        self.assertEqual(result['corpus']['source_records'], 39)
        self.assertEqual(result['pages'], 71)
        self.assertTrue((p.OUT / 'sources/mode.txt').is_file())

    def test_missing_identity_fails(self):
        file = p.OUT / 'corpus/catalog.json'
        catalog = json.loads(file.read_text(encoding='utf-8'))
        catalog['documents'].pop()
        file.write_text(json.dumps(catalog), encoding='utf-8')
        with self.assertRaises(AssertionError):
            p.validate('https://example.invalid/research', report=False)

    def test_catalog_metadata_drift_fails(self):
        file = p.OUT / 'corpus/catalog.json'
        catalog = json.loads(file.read_text(encoding='utf-8'))
        catalog['documents'][0]['title'] = 'Unrelated title'
        file.write_text(json.dumps(catalog), encoding='utf-8')
        with self.assertRaisesRegex(AssertionError, 'Catalog metadata drift'):
            p.validate('https://example.invalid/research', report=False)

    def test_required_metadata_disappearing_fails(self):
        file = p.OUT / 'systems/mode/index.html'
        raw = file.read_text(encoding='utf-8').replace('DeMarius J. Lawson', 'Someone else')
        file.write_text(raw, encoding='utf-8')
        with self.assertRaises(AssertionError):
            p.validate('https://example.invalid/research', report=False)

    def test_discovery_link_loss_fails(self):
        file = p.OUT / 'systems/mode/index.html'
        raw = file.read_text(encoding='utf-8').replace('href="../../systems/spec-cloud/index.html"', 'href="../../index.html"')
        file.write_text(raw, encoding='utf-8')
        with self.assertRaisesRegex(AssertionError, 'Related research link missing'):
            p.validate('https://example.invalid/research', report=False)

    def test_source_tampering_fails(self):
        file = p.OUT / 'sources/mode.txt'
        file.write_text('incomplete source', encoding='utf-8')
        with self.assertRaises(AssertionError):
            p.validate('https://example.invalid/research', report=False)

    def test_approved_original_artifacts_are_unmodified(self):
        import hashlib
        data, manifests = p.corpus.load()
        for identity in ('mechanism-primacy', 'ai-system-construction-method'):
            d = next(d for d in data['documents'] if d['id'] == identity)
            m = next(m for m in manifests if m['id'] == identity)
            source = (p.OUT / p.corpus.public_source_path(d)).read_bytes()
            self.assertEqual(hashlib.sha256(source).hexdigest(), m['original_sha256'])
            self.assertEqual(m['published_sha256'], m['original_sha256'])
            self.assertEqual(m['redaction_counts'], {})
            self.assertEqual(m['edition'], 'original bytes; no modifications')
        self.assertTrue((p.OUT / 'sources/ai-system-construction-method-v1-1.pdf').read_bytes().startswith(b'%PDF-'))

    def test_original_pdf_tampering_fails(self):
        with (p.OUT / 'sources/ai-system-construction-method-v1-1.pdf').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaises(AssertionError):
            p.validate('https://example.invalid/research', report=False)

    def test_extractor_cannot_rewrite_approved_original(self):
        import ingest_corpus
        with self.assertRaisesRegex(ValueError, 'extraction is prohibited'):
            ingest_corpus.ingest(p.ROOT, ['ai-system-construction-method'])

    def test_graph_dangling_node_fails(self):
        file = p.OUT / 'corpus/relationships.json'
        graph = json.loads(file.read_text(encoding='utf-8'))
        graph['edges'][0]['to'] = 'missing-source'
        file.write_text(json.dumps(graph), encoding='utf-8')
        with self.assertRaises(AssertionError):
            p.validate('https://example.invalid/research', report=False)

    def test_privacy_filter(self):
        sample = 'person@example.invalid HPPOQL-12345 card ending in 4321 https://example.invalid/join/private $99.00'
        result, counts = scrub(sample, case_study=True)
        self.assertNotIn('person@', result)
        self.assertNotIn('HPPOQL-', result)
        self.assertNotIn('4321', result)
        self.assertNotIn('/join/', result)
        self.assertNotIn('$99.00', result)
        self.assertEqual(len(counts), 5)

    def test_no_duplicate_canonical_title(self):
        from unittest.mock import patch
        from copy import deepcopy
        data = deepcopy(p.corpus.load()[0])
        data['documents'][1]['title'] = data['documents'][0]['title']
        read = p.corpus.Path.read_text
        def changed(path, *args, **kwargs):
            return json.dumps(data) if path.name == 'corpus.json' else read(path, *args, **kwargs)
        with patch.object(p.corpus.Path, 'read_text', changed):
            with self.assertRaisesRegex(AssertionError, 'Duplicate canonical document'):
                p.corpus.load()

    def test_single_stable_journey(self):
        data = p.corpus.load()[0]
        journeys = [d for d in data['documents'] if d.get('record_role') == 'cumulative-lineage']
        self.assertEqual([d['id'] for d in journeys], ['governing-engines-journey'])
        self.assertEqual(p.corpus.path(journeys[0]), 'journey/governing-engines-journey/index.html')
        self.assertEqual(p.corpus.source_file(journeys[0]), 'journey/governing-engines-journey.txt')
        self.assertTrue((p.OUT / 'journey/governing-engines-journey/source.txt').is_file())

    def test_machine_state_chronology(self):
        data = p.corpus.load()[0]
        snapshots = sorted((d for d in data['documents'] if d.get('snapshot')), key=lambda d: d['snapshot']['date'])
        self.assertEqual([d['snapshot']['date'] for d in snapshots], ['2026-09-14', '2026-10-21'])
        self.assertEqual(snapshots[0]['snapshot']['position'], 'historical')
        self.assertEqual(snapshots[1]['snapshot']['position'], 'current-public-at-cutoff')
        for d in snapshots:
            self.assertTrue((p.OUT / p.corpus.public_source_path(d)).is_file())

    def test_wrong_current_snapshot_rejected(self):
        from unittest.mock import patch
        from copy import deepcopy
        data = deepcopy(p.corpus.load()[0])
        for d in data['documents']:
            if d.get('snapshot'):
                d['snapshot']['position'] = 'current-public-at-cutoff' if d['snapshot']['date'] == '2026-09-14' else 'historical'
        read = p.corpus.Path.read_text
        def changed(path, *args, **kwargs):
            return json.dumps(data) if path.name == 'corpus.json' else read(path, *args, **kwargs)
        with patch.object(p.corpus.Path, 'read_text', changed):
            with self.assertRaisesRegex(AssertionError, 'Machine-state chronology'):
                p.corpus.load()

    def test_internal_ecosystem_not_published(self):
        data = p.corpus.load()[0]
        self.assertFalse(any('ecosystem-machine-state' in d['id'] for d in data['documents']))
        self.assertFalse(any('Internal Verified State & Traceability Record' in f.read_text(encoding='utf-8')
                             for f in p.OUT.rglob('*.txt')))

    def test_import_preserves_unselected_sources(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import ingest_corpus
        with tempfile.TemporaryDirectory(dir=p.ROOT) as temp:
            root = Path(temp)
            (root / 'content').mkdir()
            (root / 'incoming').mkdir()
            original = [{'id': 'keep', 'original_sha256': 'unchanged'}]
            (root / 'content/source-manifest.json').write_text(json.dumps(original))
            (root / 'content/corpus.json').write_text(json.dumps({'documents': [
                {'id': 'keep', 'source_pattern': 'absent.txt'},
                {'id': 'new', 'title': 'New', 'section': 'research', 'source_pattern': 'new.txt'}]}))
            (root / 'incoming/new.txt').write_text('Authorized public wording')
            with patch.object(ingest_corpus, 'ROOT', root):
                ingest_corpus.ingest(root / 'incoming', ['new'])
            manifest = json.loads((root / 'content/source-manifest.json').read_text())
            self.assertEqual(manifest[0], original[0])
            self.assertEqual(len(manifest), 2)

    def test_machine_local_path_is_redacted(self):
        result, counts = scrub(r'Traces are at C:\MODE_AI\runtime_traces\interactions.jsonl; reference https://example.invalid/paper')
        self.assertNotIn('C:', result)
        self.assertIn('https://example.invalid/paper', result)
        self.assertEqual(counts['local_filesystem_path'], 1)


if __name__ == '__main__':
    unittest.main()
