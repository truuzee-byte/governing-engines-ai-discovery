"""One-time import of authorized public handoff documents; not a build dependency.

Usage: python tools/ingest_corpus.py --source-dir DIRECTORY
Requires pypdf only for PDF import. DOCX extraction uses the standard library.
Never copies original binaries into the public output.
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


def ingest(directory):
    records = json.loads((ROOT / 'content/corpus.json').read_text(encoding='utf-8'))['documents']
    sources = ROOT / 'content/sources'
    sources.mkdir(exist_ok=True)
    evidence = []
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
        target = sources / (d['id'] + '.txt')
        target.write_text(result, encoding='utf-8', newline='\n')
        evidence.append({'id': d['id'], 'original_filename': f.name,
                         'identity': {k: d.get(k) for k in ('title', 'subtitle', 'version', 'date', 'status')},
                         'original_sha256': hashlib.sha256(f.read_bytes()).hexdigest(),
                         'published_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                         'source_pdf_pages': pages, 'redaction_counts': counts,
                         'edition': 'privacy-filtered text extraction; original binary not distributed'})
    (ROOT / 'content/source-manifest.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Imported {len(evidence)} authorized public source text editions')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir', type=Path, required=True)
    ingest(p.parse_args().source_dir)
