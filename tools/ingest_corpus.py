"""One-time import of authorized public handoff documents; not a build dependency.

Usage: python tools/ingest_corpus.py --source-dir DIRECTORY
Requires pypdf only for PDF import. DOCX extraction uses the standard library.
Never copies original binaries into the public output.
Approved byte-original records are preserved, never passed through this extractor.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def scrub(text, case_study=False):
    patterns = {
        'email_address': r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',
        'invoice_identifier': r'\bHPPOQL-\d+\b',
        'credential': r'(?:gh[pousr]_|github_pat_|sk-proj-)[A-Za-z0-9_-]{15,}',
        'private_access_url': r'https?://[^\s<>]*(?:[?&](?:token|key|access_token)=|/join/|/invite/)[^\s<>]*',
        'account_url': r'https?://(?:www\.)?replit\.com/@[^\s<>]+',
        'payment_instrument': r'(?i)(?:card|account)\s+(?:ending\s+(?:in\s+)?)\d{4}',
        'local_filesystem_path': r'\b[A-Za-z]:[\\/][^\s<>"\r\n]+',
    }
    if case_study:
        patterns['billing_amount'] = r'\$\s*\d[\d,]*(?:\.\d{2})?'
    counts = {}
    for name, pattern in patterns.items():
        text, count = re.subn(pattern, '[REDACTED: ' + name.replace('_', ' ') + ']', text, flags=re.I)
        if count:
            counts[name] = count
    return text, counts


def extract(path):
    if path.suffix.lower() == '.pdf':
        from pypdf import PdfReader
        r = PdfReader(path)
        return '\n\n'.join(f'[Source PDF page {i}]\n' + (p.extract_text() or '')
                           for i, p in enumerate(r.pages, 1)), len(r.pages)
    if path.suffix.lower() == '.docx':
        with zipfile.ZipFile(path) as z:
            xml = ET.fromstring(z.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        return '\n'.join(''.join(p.itertext()) for p in xml.findall('.//w:p', ns)), None
    return path.read_text(encoding='utf-8-sig'), None


def ingest(directory, ids=None):
    records = json.loads((ROOT / 'content/corpus.json').read_text(encoding='utf-8'))['documents']
    manifest_path = ROOT / 'content/source-manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else []
    originals = {m['id'] for m in previous if m.get('edition') == 'original bytes; no modifications'}
    if ids and originals.intersection(ids):
        raise ValueError('Approved originals require explicit byte-preserving review; extraction is prohibited')
    if ids:
        assert set(ids) <= {d['id'] for d in records}, 'Unknown import ID'
        records = [d for d in records if d['id'] in ids]
    records = [d for d in records if d['id'] not in originals]
    sources = ROOT / 'content/sources'
    sources.mkdir(exist_ok=True)
    evidence = {m['id']: m for m in previous}
    for d in records:
        matches = list(directory.glob(d['source_pattern']))
        if len(matches) != 1:
            raise ValueError(f'Expected one source for {d["id"]}, found {len(matches)}')
        f = matches[0]
        raw, pages = extract(f)
        text, counts = scrub(raw, d['section'] == 'case-studies')
        header = ('PUBLIC SOURCE TEXT EDITION\n' + d['title'] + '\n'
                  'Source supplied by the author for public research discovery.\n'
                  'Text extracted from the supplied artifact; layout, tables and pagination may differ.\n'
                  'Privacy filtering is marked inline. This is not the original binary artifact.\n\n')
        result = '\n'.join(line.rstrip() for line in (header + text).splitlines()).rstrip() + '\n'
        target = ROOT / 'content' / d.get('source_file', 'sources/' + d['id'] + '.txt')
        assert (ROOT / 'content').resolve() in target.resolve().parents, 'Source outside content directory'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result, encoding='utf-8', newline='\n')
        evidence[d['id']] = {'id': d['id'], 'original_filename': f.name,
                         'identity': {k: d.get(k) for k in ('title', 'subtitle', 'version', 'date', 'status')},
                         'original_sha256': hashlib.sha256(f.read_bytes()).hexdigest(),
                         'published_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                         'source_pdf_pages': pages, 'redaction_counts': counts,
                         'edition': 'privacy-filtered text extraction; original binary not distributed'}
    manifest_path.write_text(json.dumps(list(evidence.values()), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Imported {len(records)} selected public editions; manifest contains {len(evidence)} records')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir', type=Path, required=True)
    p.add_argument('--ids', nargs='+', help='Import only audited IDs; preserve all other source editions and manifest entries')
    args = p.parse_args()
    ingest(args.source_dir, args.ids)
