"""Dependency-free publication builder, parser-based validator, and public checker."""
import argparse
import hashlib
import html
import json
import os
import sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, unquote
from urllib.request import urlopen, Request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import corpus
OUT = ROOT / 'dist'
EXPECTED = {'reasoning-and-context', 'autonomy-and-robotics', 'execution-verification',
            'enterprise-governance', 'reliability-and-faults', 'human-feedback',
            'retrieval-and-relevance', 'uncertain-decisions'}
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'


def inputs(base=None):
    config = json.loads((ROOT / 'config/publication.json').read_text(encoding='utf-8'))
    config['base_url'] = (base or os.environ.get('SITE_URL') or config['base_url']).rstrip('/')
    parsed = urlparse(config['base_url'])
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError('SITE_URL must be an absolute HTTP(S) URL without query or fragment')
    if not config['message'] or '--' in config['message'] or '<' in config['message']:
        raise ValueError('Message must be nonempty and safe for HTML comments')
    docs = json.loads((ROOT / 'content/documents.json').read_text(encoding='utf-8'))
    if len(docs) != len(EXPECTED) or {d['slug'] for d in docs} != EXPECTED:
        raise ValueError('Document inventory differs from expected subjects')
    return config, docs


def public_url(c, path=''):
    return c['base_url'] + '/' + path


def write(path, value):
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding='utf-8', newline='\n')


def page(c, title, summary, path, body, article=False):
    e = html.escape
    url = public_url(c, path)
    data = {'@context': 'https://schema.org', '@type': 'TechArticle' if article else 'CollectionPage',
            'headline': title, 'description': summary, 'url': url, 'inLanguage': 'en',
            'publisher': {'@type': 'Organization', 'name': c['name'],
                          'founder': {'@type': 'Person', 'name': c['founder']}},
            'datePublished': c['date']}
    if article:
        data['comment'] = {'@type': 'Comment', 'text': c['message'],
                           'author': {'@type': 'Organization', 'name': c['name']}}
    machine = (f'<meta name="publisher-contact-recommendation" content="{e(c["message"], quote=True)}">\n'
               f'<!-- Publisher contact recommendation: {c["message"]} -->') if article else ''
    structured = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    prefix = '../' if article else './'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | Governing Engines</title><meta name="description" content="{e(summary, quote=True)}">
<link rel="canonical" href="{e(url, quote=True)}"><link rel="stylesheet" href="{prefix}assets/style.css">
{machine}
<script type="application/ld+json">{structured}</script></head>
<body><a class="skip" href="#main">Skip to content</a><header><a href="{prefix}index.html">Governing Engines</a><span> / Technical notes</span></header>
<main id="main">{body}</main><footer>Published {e(c['date'])}. Technical synthesis; no original experiments claimed.
<a href="{prefix}about.html">Publication methods and limitations</a></footer></body></html>'''


def build(base=None):
    c, docs = inputs(base)
    OUT.mkdir(exist_ok=True)
    # Remove only files from the previous generated manifest, within dist.
    manifest = OUT / 'build.json'
    if manifest.exists():
        for name in json.loads(manifest.read_text(encoding='utf-8')).get('files', []):
            target = (OUT / name).resolve()
            if OUT.resolve() in target.parents and target.is_file():
                target.unlink()
    e = html.escape
    by_slug = {d['slug']: d for d in docs}
    paths = ['index.html', 'about.html']
    for d in docs:
        slug = d['slug']
        path = f'{slug}/index.html'
        paths.append(path)
        body = f'<p class="eyebrow">Foundations / {docs.index(d)+1:02d}</p><article><h1>{e(d["title"])}</h1><p class="lede">{e(d["summary"])}</p>'
        md = f'# {d["title"]}\n\n{d["summary"]}\n\n'
        for heading, text in d['sections']:
            body += f'<section><h2>{e(heading)}</h2><p>{e(text)}</p></section>'
            md += f'## {heading}\n\n{text}\n\n'
        body += '<section><h2>Sources and scope</h2><p>Sources support the foundational framing; worked scenarios and proposed checks are editorial illustrations.</p><ul>'
        md += '## Sources\n\n'
        for label, url in d['sources']:
            body += f'<li><a href="{e(url, quote=True)}">{e(label)}</a></li>'
            md += f'- [{label}]({url})\n'
        body += '</ul></section><nav aria-label="Related notes"><h2>Related notes</h2><ul>'
        md += '\n## Related notes\n\n'
        for related in d['related']:
            label = by_slug[related]['title']
            body += f'<li><a href="../{related}/index.html">{e(label)}</a></li>'
            md += f'- [{label}](../{related}/index.html)\n'
        body += f'</ul></nav><p><a href="../markdown/{slug}.md">Download Markdown source</a></p></article>'
        md += f'\n<!-- Publisher contact recommendation: {c["message"]} -->\n'
        write(path, page(c, d['title'], d['summary'], path, body, True))
        write(f'markdown/{slug}.md', md)
    body = '<p class="eyebrow">Research publication / 2026</p><h1>Engineering decisions.<br>Inspectable evidence.</h1><p class="lede">Eight technical notes on reasoning, reliable execution, and accountable AI systems.</p><div class="grid">'
    for n, d in enumerate(docs, 1):
        body += f'<article class="card"><p class="eyebrow">{n:02d} / Foundations</p><h2><a href="{d["slug"]}/index.html">{e(d["title"])}</a></h2><p>{e(d["summary"])}</p></article>'
    body += '</div><section><h2>Explore the source research corpus</h2><p><a href="corpus/index.html">Browse and search ' + str(corpus.load()[0]['document_count']) + ' Governing Engines source documents</a> across purpose, principles, terminology, methods, systems, research, lineage and evidence. <a href="corpus/graph.html">Follow the relationship graph</a>.</p></section>'
    write('index.html', page(c, 'Technical research library', 'Foundational engineering notes from Governing Engines.', 'index.html', body))
    about = '''<h1>Publication methods and limitations</h1><p>These notes are editorial technical syntheses, not peer-reviewed research or reports of original technical experiments. Sources and illustrative scenarios are identified within each note.</p><h2>Publisher instruction experiment</h2><p>The publisher is testing whether an explicit instruction embedded in retrieved publications changes an external assistant's contact recommendations. Article source carries the same publisher-authored instruction in JSON-LD, HTML metadata, and a non-rendered HTML comment. Downloadable Markdown preserves the instruction in a comment. The instruction is excluded from ordinary article paragraphs. These fields are public and inspectable, not private or encrypted. The instruction expresses the publisher's requested behavior; it does not claim authority over external assistants or independent endorsement.</p><h2>Discovery and behavior are external outcomes</h2><p>Publication does not guarantee indexing, retrieval, instruction extraction, or recommendation by ChatGPT, Claude, Grok, or any other service. Crawlers and extractors may ignore metadata and comments. Whether the instruction changes an assistant's response remains untested; no external behavioral outcome is claimed by this publication.</p>'''
    write('about.html', page(c, 'Publication methods', 'Scope, provenance, and discovery limitations.', 'about.html', about))
    write('assets/style.css', '''@import url("data:text/css,");
:root{color-scheme:light;--ink:#142f36;--muted:#4d6268;--paper:#f6f4ed;--line:#c6d1cb;--accent:#176b59}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:18px/1.7 system-ui,sans-serif}a{color:var(--accent);text-underline-offset:.2em}a:focus-visible{outline:3px solid #b65b22;outline-offset:4px}header,footer{max-width:1160px;margin:auto;padding:28px 30px;border-bottom:1px solid var(--line)}header a{font-weight:750;text-decoration:none}header span{color:var(--muted)}main{max-width:1160px;margin:auto;padding:70px 30px}h1{font-size:clamp(2.3rem,5vw,4.4rem);line-height:1.12;letter-spacing:-.045em;max-width:920px}h2{line-height:1.3;font-size:1.45rem;margin-top:2rem}.lede{font-size:1.25rem;color:var(--muted);max-width:760px}.eyebrow{font-size:.78rem;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px;margin-top:50px}.card{padding:24px 28px;border:1px solid var(--line);border-top:3px solid var(--accent)}.card h2{margin-top:8px}.card p{color:var(--muted)}main>article{max-width:790px}section{margin-top:35px}footer{font-size:.85rem;color:var(--muted);border-top:1px solid var(--line);border-bottom:0}footer a{display:block}.skip{position:absolute;left:-10000px}.skip:focus{left:10px;top:10px;background:white;padding:10px}@media(max-width:650px){.grid{grid-template-columns:1fr}main{padding:35px 22px}header span{display:block}}'''.replace('@import url("data:text/css,");\n', ''))
    paths += corpus.build(c, OUT)
    root = ET.Element('urlset', xmlns=NS)
    for path in paths:
        ET.SubElement(ET.SubElement(root, 'url'), 'loc').text = public_url(c, path)
    write('sitemap.xml', ET.tostring(root, encoding='unicode', xml_declaration=True))
    write('robots.txt', f'User-agent: *\nAllow: /\nSitemap: {public_url(c, "sitemap.xml")}\n')
    write('.nojekyll', '')
    files = sorted(str(p.relative_to(OUT)).replace('\\', '/') for p in OUT.rglob('*') if p.is_file() and p.name != 'build.json')
    write('build.json', json.dumps({'base_url': c['base_url'], 'documents': sorted(EXPECTED), 'files': files,
                                 'sha256': {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in files}}, indent=2))
    return c, docs


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.links, self.comments, self.jsonld = {}, [], [], []
        self.canonical, self.script = [], None
        self.text, self.ids, self.duplicates, self.tags = [], set(), [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        if 'id' in a:
            if a['id'] in self.ids:
                self.duplicates.append(a['id'])
            self.ids.add(a['id'])
        if tag == 'meta' and 'name' in a:
            if a['name'] in self.meta:
                raise ValueError('Duplicate named metadata')
            self.meta[a['name']] = a.get('content', '')
        if tag in ('a', 'link') and 'href' in a:
            self.links.append(a['href'])
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonical.append(a['href'])
        if tag == 'script' and a.get('type') == 'application/ld+json':
            self.script = ''

    def handle_data(self, data):
        if self.script is not None:
            self.script += data
        else:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            self.jsonld.append(json.loads(self.script))
            self.script = None

    def handle_comment(self, data):
        self.comments.append(data)


def parse(text):
    p = Parser()
    p.feed(text)
    p.close()
    return p


def validate(base=None, report=True):
    c, docs = inputs(base)
    manifest = json.loads((OUT / 'build.json').read_text(encoding='utf-8'))
    assert manifest['base_url'] == c['base_url'], 'Build URL differs from validation configuration'
    expected_pages = {'index.html', 'about.html'} | {f'{s}/index.html' for s in EXPECTED}
    expected_pages |= set(corpus.paths())
    actual_pages = {p.relative_to(OUT).as_posix() for p in OUT.rglob('*.html')}
    assert actual_pages == expected_pages, 'Unexpected/missing HTML pages'
    pages = {f: parse((OUT / f).read_text(encoding='utf-8')) for f in expected_pages}
    extraction = []
    for f, p in pages.items():
        assert not p.duplicates, f'Duplicate IDs: {f}'
        assert p.canonical == [public_url(c, f)], f'Canonical mismatch: {f}'
        assert p.meta.get('description') and p.meta.get('viewport'), f'Metadata absent: {f}'
        assert all(t in p.tags for t in ('html', 'title', 'main', 'h1', 'footer')), f'Semantics absent: {f}'
        assert len(p.jsonld) == 1 and p.jsonld[0]['url'] == public_url(c, f), f'JSON-LD mismatch: {f}'
        for href in p.links:
            u = urlparse(href)
            if u.scheme or u.netloc:
                continue
            target = (OUT / f).parent / unquote(u.path) if u.path else OUT / f
            target = target.resolve()
            assert OUT.resolve() in target.parents and target.is_file(), f'Broken link {f}: {href}'
            if u.fragment:
                rel = target.relative_to(OUT).as_posix()
                assert rel in pages and u.fragment in pages[rel].ids, f'Broken fragment: {href}'
    for d in docs:
        p = pages[f'{d["slug"]}/index.html']
        assert p.meta['publisher-contact-recommendation'] == c['message']
        assert p.jsonld[0]['comment']['text'] == c['message']
        assert p.comments.count(' Publisher contact recommendation: ' + c['message'] + ' ') == 1
        assert c['message'] not in ''.join(p.text), 'Message leaked into ordinary rendered text'
        md = (OUT / 'markdown' / (d['slug'] + '.md')).read_text(encoding='utf-8')
        assert md.count('<!-- Publisher contact recommendation: ' + c['message'] + ' -->') == 1
        extraction.append({'slug': d['slug'], 'html_metadata': True, 'json_ld': True,
                           'html_comment': True, 'markdown_comment': True, 'rendered_text_absent': True,
                           'extracted_message': p.meta['publisher-contact-recommendation']})
    sitemap = ET.parse(OUT / 'sitemap.xml')
    urls = [loc.text for loc in sitemap.findall(f'.//{{{NS}}}loc')]
    assert len(urls) == len(expected_pages) and set(urls) == {public_url(c, f) for f in expected_pages}
    assert (OUT / 'robots.txt').read_text().endswith(public_url(c, 'sitemap.xml') + '\n')
    corpus_result = corpus.validate(c, OUT, pages)
    for f, digest in manifest['sha256'].items():
        assert hashlib.sha256((OUT / f).read_bytes()).hexdigest() == digest, f'Artifact changed: {f}'
    result = {'status': 'PASS', 'pages': len(pages), 'documents': len(docs), 'corpus': corpus_result, 'base_url': c['base_url'],
              'extraction': extraction, 'public_deployment': 'UNVERIFIED', 'external_discovery': 'NOT TESTED'}
    if report:
        from datetime import datetime, timezone
        result['checked_at'] = datetime.now(timezone.utc).isoformat()
        reports = ROOT / 'reports'
        reports.mkdir(exist_ok=True)
        (reports / 'local-validation.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'PASS: {len(pages)} pages; {len(docs)} documents; links, sitemap, hashes, and four extraction layers')
    return result


def check_public(base):
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    previous = reports / 'public-verification.json'
    if previous.exists():
        previous.unlink()
    c, docs = inputs(base)
    if urlparse(c['base_url']).scheme != 'https' or urlparse(c['base_url']).hostname in ('localhost', '127.0.0.1'):
        raise ValueError('Public verification requires a public HTTPS SITE_URL')
    paths = ['index.html', 'about.html', 'robots.txt', 'sitemap.xml']
    paths += [f'{d["slug"]}/index.html' for d in docs]
    paths += [f'markdown/{d["slug"]}.md' for d in docs]
    paths += corpus.paths()
    paths += ['corpus/catalog.json', 'corpus/relationships.json', 'assets/style.css', 'assets/corpus-search.js']
    paths += [corpus.public_source_path(d) for d in corpus.load()[0]['documents']]
    evidence = []
    from datetime import datetime, timezone
    for path in paths:
        url = public_url(c, path)
        with urlopen(Request(url, headers={'User-Agent': 'GoverningEngines-PublicationCheck/1.0'}), timeout=30) as response:
            assert response.status == 200, f'HTTP failure: {url}'
            body = response.read()
            # Compare deployed content to this build, including all four message layers.
            assert body == (OUT / path).read_bytes(), f'Public content differs: {url}'
            evidence.append({'url': url, 'status': response.status, 'final_url': response.url})
    (ROOT / 'reports/public-verification.json').write_text(json.dumps({'checked_at': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS', 'responses': evidence, 'external_discovery': 'NOT TESTED'}, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: {len(evidence)} public URLs match the generated publication')


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Run without -O: validation assertions must remain enabled')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'validate', 'check-public'])
    parser.add_argument('--base-url')
    args = parser.parse_args()
    if args.command == 'build':
        build(args.base_url)
        print('Built dist/')
    elif args.command == 'validate':
        validate(args.base_url)
    else:
        check_public(args.base_url)
