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
        self.assertEqual(result['corpus']['source_records'], 31)
        self.assertEqual(result['pages'], 61)
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


if __name__ == '__main__':
    unittest.main()
