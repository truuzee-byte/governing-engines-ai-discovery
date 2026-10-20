"""Static research catalog extension. No runtime dependencies beyond Python."""
import hashlib
import html
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = {'core': 'Purpose, principles and terminology', 'methods': 'Methods',
            'systems': 'Systems and public build specifications', 'research': 'Research',
            'case-studies': 'Evidence-linked case studies'}
GROUPS = {'ai-risk-and-proof': 'AI risk, execution and proof', 'reality-primacy': 'Reality primacy',
          'research-and-discovery': 'Research and discovery', 'economics-and-labor': 'Economics and labor',
          'systems-and-institutions': 'Systems and institutions', 'physical-and-quantum': 'Physical and quantum systems'}
CONCEPTS = {
    'execution-evidence': ('Execution evidence', 'Proof that an action occurred must be distinguished from an output or completion claim.', ['mode', 'runtime-observation-refinement', 'replit-provenance', 'governed-tevv']),
    'outcome-validation': ('Outcome validation', 'Execution is distinct from the valid outcome and its observable consequences.', ['mode', 'governed-tevv', 'the-cost-of-the-outcome']),
    'reality-primacy': ('Reality primacy', 'Representations and claims remain subject to contradictory evidence and external consequences.', ['before-you-name-the-machine', 'what-is-intelligence', 'human-abstractions', 'ai-doom']),
    'authority': ('Authority and admissibility', 'Capability, provenance, observation authority, execution authority and spend authority are distinct.', ['governing-principles', 'governed-tevv', 'replit-cross-system-authority']),
    'semantic-continuity': ('Semantic continuity', 'Preserve material meaning, scope, correction and lineage through system transitions.', ['canonical-terminology', 'semantic-compression', 'spec-cloud', 'mode']),
    'research-custody': ('Research custody', 'A research artifact is not the entire inquiry, its corrections, or its evidence lineage.', ['the-mask-ai-research-wears', 'past-present-future', 'semantic-compression']),
    'physical-systems': ('Physical systems', 'A proposed architecture needs platform-specific realization and independent physical outcome checks.', ['governed-adaptive-quantum-control', 'before-we-arrive', 'past-present-future']),
}
CHAIN = ['responsible-human-stewardship', 'governing-principles', 'canonical-terminology',
         'operator-governance', 'mode', 'spec-cloud', 'governed-tevv',
         'runtime-observation-refinement', 'execution-evidence', 'outcome-validation', 'reality-primacy']
PROOF_CHAIN = ['execution-evidence', 'authority', 'governed-tevv', 'mode', 'operator-governance',
               'semantic-continuity', 'reality-primacy', 'research-custody', 'physical-systems']


def load():
    data = json.loads((ROOT / 'content/corpus.json').read_text(encoding='utf-8'))
    docs = data['documents']
    manifests = json.loads((ROOT / 'content/source-manifest.json').read_text(encoding='utf-8'))
    by_id = {d['id']: d for d in docs}
    assert len(by_id) == len(docs) == len(manifests) == 31, 'Corpus inventory must contain 31 unique sources'
    assert set(by_id) == {m['id'] for m in manifests}, 'Source identities differ'
    for d in docs:
        assert re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', d['id']), 'Invalid stable identifier'
        assert d['section'] in SECTIONS and d['group'] in GROUPS
        assert d['title'] and d['abstract'] and d['status'] and d['boundary']
        assert 'version' in d and 'date' in d
        assert 5 <= len(d['terms']) <= 15 and len(set(d['terms'])) == len(d['terms'])
        assert 3 <= len(d['claims']) <= 8 and 3 <= len(d['related']) <= 8
        assert len(set(d['related'])) == len(d['related'])
        assert all(r in by_id and r != d['id'] for r in d['related']), 'Unknown related document'
        m = next(m for m in manifests if m['id'] == d['id'])
        assert m['identity'] == {k: d.get(k) for k in ('title', 'subtitle', 'version', 'date', 'status')}, 'Source identity drift'
        source = ROOT / 'content/sources' / (d['id'] + '.txt')
        assert hashlib.sha256(source.read_bytes()).hexdigest() == m['published_sha256'], 'Source hash mismatch'
    return data, manifests


def path(d):
    return d['section'] + '/' + d['id'] + '/index.html'


def paths():
    data, _ = load()
    return ([path(d) for d in data['documents']] + ['corpus/index.html', 'corpus/graph.html']
            + [s + '/index.html' for s in SECTIONS]
            + ['research/' + g + '/index.html' for g in GROUPS]
            + ['concepts/' + k + '/index.html' for k in CONCEPTS])


def shell(config, file, title, description, body, structured=None):
    e = html.escape
    prefix = '../' * (len(Path(file).parts) - 1)
    url = config['base_url'] + '/' + file
    ld = structured or {'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': title,
                        'description': description, 'url': url, 'inLanguage': 'en'}
    ld['url'] = url
    ld.setdefault('publisher', {'@type': 'Organization', 'name': 'Governing Engines LLC'})
    encoded = json.dumps(ld, ensure_ascii=False).replace('<', '\\u003c')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | Governing Engines research</title><meta name="description" content="{e(description, quote=True)}">
<link rel="canonical" href="{e(url, quote=True)}"><link rel="stylesheet" href="{prefix}assets/style.css">
<script type="application/ld+json">{encoded}</script></head><body><a class="skip" href="#main">Skip to content</a>
<header><a href="{prefix}index.html">Governing Engines</a><nav aria-label="Research navigation"><a href="{prefix}corpus/index.html">Corpus and search</a> · <a href="{prefix}corpus/graph.html">Relationships</a> · <a href="{prefix}corpus/catalog.json">JSON catalog</a></nav></header>
<main id="main">{body}</main><footer>Discovery record published 2026-10-20. Summaries and reading relationships are editorial; source claims retain their stated limits.
<a href="{prefix}about.html">Publication methods</a></footer></body></html>'''


def build(config, out):
    data, manifests = load()
    docs = data['documents']
    by_id = {d['id']: d for d in docs}
    e = html.escape

    def write(file, value):
        p = out / file
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value, encoding='utf-8', newline='\n')

    def links(records, prefix):
        return '<ul>' + ''.join(f'<li><a href="{prefix}{path(d)}">{e(d["title"])}</a> — {e(d["abstract"])}</li>' for d in records) + '</ul>'

    catalog = {'schema_version': '1.0', 'edition_date': data['edition_date'], 'author': data['author'],
               'organization': data['organization'],
               'scope': 'Author-supplied public documents; editorial summaries; no independent verification of source empirical claims.',
               'documents': []}
    for d in docs:
        m = next(m for m in manifests if m['id'] == d['id'])
        file = path(d)
        source_path = 'sources/' + d['id'] + '.txt'
        record = {k: v for k, v in d.items() if k != 'source_pattern'}
        record.update({'author': data['author'], 'organization': data['organization'],
                       'url': config['base_url'] + '/' + file,
                       'source_url': config['base_url'] + '/' + source_path, 'provenance': m})
        catalog['documents'].append(record)
        (out / 'sources').mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'content/sources' / (d['id'] + '.txt'), out / source_path)
        ld = {'@context': 'https://schema.org', '@type': 'CreativeWork', 'name': d['title'],
              'description': d['abstract'], 'author': {'@type': 'Person', 'name': data['author']},
              'keywords': d['terms'], 'inLanguage': 'en', 'datePublished': data['edition_date'],
              'isBasedOn': {'@type': 'CreativeWork', 'name': d['title'], 'url': record['source_url']}}
        if d['version']:
            ld['isBasedOn']['version'] = d['version']
        if d['date'] and re.fullmatch(r'\d{4}-\d{2}-\d{2}', d['date']):
            ld['isBasedOn']['datePublished'] = d['date']
        body = f'<p class="eyebrow">{e(SECTIONS[d["section"]])} / Source record</p><article><h1>{e(d["title"])}</h1>'
        if d.get('subtitle'):
            body += '<p class="lede">' + e(d['subtitle']) + '</p>'
        body += f'<p>Author: <strong>{e(data["author"])}</strong><br>Organization: {e(data["organization"])}</p><dl>'
        for label, value in [('Source version', d['version']), ('Source date', d['date']), ('Source status', d['status'])]:
            body += f'<dt>{label}</dt><dd>{e(value or "Not stated in supplied source")}</dd>'
        body += '</dl><section><h2>Source-faithful abstract</h2><p>' + e(d['abstract']) + '</p></section>'
        body += '<section><h2>Core claims and distinctions</h2><p>The following summarize the source author’s positions; they are not independent validation.</p><ul>'
        body += ''.join('<li>' + e(x) + '</li>' for x in d['claims']) + '</ul></section>'
        body += '<section><h2>Claim boundaries and evidence posture</h2><p>' + e(d['boundary']) + '</p></section>'
        body += '<section><h2>Research terms</h2><ul>' + ''.join('<li>' + e(t) + '</li>' for t in d['terms']) + '</ul></section>'
        body += f'<section><h2>Inspectable source</h2><p><a href="../../{source_path}">Read or download the public source text edition</a>. '
        body += 'This extraction preserves the supplied wording with marked privacy redactions; it is not the original PDF/DOCX or a layout-faithful replacement. PDF page markers identify source pages. DOCX tables and mathematical notation may require the original for visual interpretation.</p>'
        body += f'<p>Original artifact: {e(m["original_filename"])}<br>Original SHA-256: <code>{m["original_sha256"]}</code><br>Published text SHA-256: <code>{m["published_sha256"]}</code></p>'
        body += '<p>Privacy redaction counts: ' + e(json.dumps(m['redaction_counts'], sort_keys=True)) + '</p></section>'
        body += '<nav aria-label="Related research"><h2>Related reading</h2><p>Editorial conceptual links, not evidence of endorsement or equivalent validation.</p>' + links([by_id[r] for r in d['related']], '../../') + '</nav>'
        body += f'<p><a href="../../{d["section"]}/index.html">Browse this collection</a> · <a href="../../research/{d["group"]}/index.html">Browse related research topic</a></p></article>'
        write(file, shell(config, file, d['title'], d['abstract'], body, ld))

    intro = '<p class="eyebrow">Public research corpus / 31 source documents</p><h1>Purpose, systems, research and evidence.</h1><p class="lede">Research questions lead to source documents, technical specifications, and evidence-linked cases.</p><p>Publication, indexing, retrieval, adoption, implementation, validation and endorsement are distinct outcomes. These records do not establish any of the latter outcomes.</p>'
    sections = '<nav aria-label="Collections"><h2>Collections</h2><ul>' + ''.join(f'<li><a href="../{s}/index.html">{e(label)}</a></li>' for s, label in SECTIONS.items()) + '</ul></nav>'
    topics = '<nav aria-label="Topics"><h2>Research topics</h2><ul>' + ''.join(f'<li><a href="../research/{g}/index.html">{e(label)}</a></li>' for g, label in GROUPS.items()) + '</ul></nav>'
    search = '<section aria-labelledby="source-list"><h2 id="source-list">Find a source</h2><label for="corpus-search">Filter titles, abstracts, research terms and claims</label><input id="corpus-search" type="search" style="display:block;max-width:100%;width:42rem;padding:.8rem;font:inherit" placeholder="For example: proof of execution, TCVO, authority"><p id="search-count" role="status" aria-live="polite">31 source records</p><noscript>All records are listed below; use your browser’s find function.</noscript><div id="corpus-records">'
    for d in docs:
        tokens = ' '.join([d['title'], d['abstract'], d['section'], *d['terms'], *d['claims']])
        search += '<article class="card" data-search="' + e(tokens.lower(), quote=True) + '"><h3><a href="../' + path(d) + '">' + e(d['title']) + '</a></h3><p>' + e(d['abstract']) + '</p><p>' + e(' · '.join(d['terms'])) + '</p></article>'
    search += '</div></section><script src="../assets/corpus-search.js" defer></script>'
    write('corpus/index.html', shell(config, 'corpus/index.html', 'Research corpus', 'Source-linked Governing Engines research, public specifications, methods and case studies.', intro + sections + topics + search))
    write('assets/corpus-search.js', "const field=document.getElementById('corpus-search');const records=[...document.querySelectorAll('[data-search]')];field.addEventListener('input',()=>{const terms=field.value.toLowerCase().trim().split(/\\s+/).filter(Boolean);let count=0;for(const r of records){r.hidden=!terms.every(t=>r.dataset.search.includes(t));if(!r.hidden)count++;}document.getElementById('search-count').textContent=count+' source record'+(count===1?'':'s');});\n")
    for s, title in SECTIONS.items():
        records = [d for d in docs if d['section'] == s]
        file = s + '/index.html'
        write(file, shell(config, file, title, 'Browse source documents: ' + title, '<h1>' + e(title) + '</h1>' + links(records, '../')))
    for g, title in GROUPS.items():
        records = [d for d in docs if d['group'] == g]
        file = 'research/' + g + '/index.html'
        write(file, shell(config, file, title, 'Research connections: ' + title, '<h1>' + e(title) + '</h1><p>A thematic reading group, not a claim that all listed works have the same evidentiary status.</p>' + links(records, '../../')))
    for key, (title, summary, ids) in CONCEPTS.items():
        file = 'concepts/' + key + '/index.html'
        write(file, shell(config, file, title, summary, '<h1>' + e(title) + '</h1><p>' + e(summary) + '</p><h2>Inspect the source distinctions</h2>' + links([by_id[i] for i in ids], '../../')))
    nodes = {d['id']: {'id': d['id'], 'title': d['title'], 'path': path(d), 'type': 'source-record'} for d in docs}
    nodes.update({k: {'id': k, 'title': v[0], 'path': 'concepts/' + k + '/index.html', 'type': 'concept'} for k, v in CONCEPTS.items()})
    edges = [{'from': d['id'], 'to': r, 'relationship': 'relatedReading'} for d in docs for r in d['related']]
    for chain in (CHAIN, PROOF_CHAIN):
        edges += [{'from': a, 'to': b, 'relationship': 'suggestedReadingSequence'} for a, b in zip(chain, chain[1:])]
    for key, (_, _, ids) in CONCEPTS.items():
        edges += [{'from': key, 'to': i, 'relationship': 'conceptReading'} for i in ids]
    graph = {'relationship_scope': 'Editorial reading graph; not an independent proof, endorsement or automatic inheritance claim.', 'nodes': list(nodes.values()), 'edges': edges}
    body = '<h1>Research relationship graph</h1><p>' + e(graph['relationship_scope']) + '</p>'
    for title, chain in [('Purpose to reality-confirmed outcomes', CHAIN), ('Execution to physical systems', PROOF_CHAIN)]:
        body += '<h2>' + title + '</h2><ol>' + ''.join('<li><a href="../' + nodes[k]['path'] + '">' + e(nodes[k]['title']) + '</a></li>' for k in chain) + '</ol>'
    body += '<h2>Concept entry points</h2><ul>' + ''.join('<li><a href="../' + nodes[k]['path'] + '">' + e(v[0]) + '</a> — ' + e(v[1]) + '</li>' for k, v in CONCEPTS.items()) + '</ul>'
    body += '<p><a href="relationships.json">Download the full relationship graph as JSON</a></p><h2>Case study chronology</h2><p>Read the authorization and historical unresolved-provenance records alongside the later cross-system attribution update. Later findings do not silently replace the earlier published evidence state.</p>' + links([by_id[k] for k in ['replit-authorization', 'replit-provenance', 'replit-cross-system-authority']], '../')
    write('corpus/graph.html', shell(config, 'corpus/graph.html', 'Research relationship graph', 'Navigate purpose, principles, methods, systems, execution proof, and evidence.', body))
    write('corpus/catalog.json', json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    write('corpus/relationships.json', json.dumps(graph, ensure_ascii=False, indent=2) + '\n')
    return paths()


def validate(config, out, parsed):
    data, manifests = load()
    catalog = json.loads((out / 'corpus/catalog.json').read_text(encoding='utf-8'))
    assert len(catalog['documents']) == 31
    assert catalog['author'] == data['author'] and catalog['organization'] == data['organization']
    by_id = {d['id']: d for d in data['documents']}
    assert {d['id'] for d in catalog['documents']} == set(by_id)
    for record in catalog['documents']:
        d = by_id[record['id']]
        for key in ('title', 'subtitle', 'date', 'version', 'status', 'abstract', 'boundary', 'claims', 'terms', 'related'):
            assert record.get(key) == d.get(key), f'Catalog metadata drift: {key}'
        p = parsed[path(d)]
        visible = ' '.join(p.text)
        assert d['title'] in visible and d['abstract'] in visible and d['boundary'] in visible
        assert data['author'] in visible and data['organization'] in visible
        assert all(t in visible for t in d['terms']) and all(x in visible for x in d['claims'])
        assert p.jsonld[0]['name'] == d['title'] and p.jsonld[0]['author']['name'] == data['author']
        assert p.jsonld[0]['isBasedOn']['url'] == record['source_url']
        assert '../../sources/' + d['id'] + '.txt' in p.links, 'Source link missing'
        for r in d['related']:
            assert '../../' + path(by_id[r]) in p.links, 'Related research link missing'
        source = out / 'sources' / (d['id'] + '.txt')
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record['provenance']['published_sha256']
        assert re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|HPPOQL-\d+|(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_-]{15,}', source.read_text(encoding='utf-8')) is None, 'Sensitive source pattern'
    graph = json.loads((out / 'corpus/relationships.json').read_text(encoding='utf-8'))
    node_ids = {n['id'] for n in graph['nodes']}
    assert node_ids == set(by_id) | set(CONCEPTS)
    assert all(e['from'] in node_ids and e['to'] in node_ids for e in graph['edges'])
    assert len(graph['edges']) >= 100
    assert all(n['path'] in parsed for n in graph['nodes'])
    actual = {(e['from'], e['to']) for e in graph['edges']}
    assert all((a, b) in actual for chain in (CHAIN, PROOF_CHAIN) for a, b in zip(chain, chain[1:]))
    assert 'corpus/index.html' in parsed['index.html'].links, 'Corpus unreachable from homepage'
    index_links = parsed['corpus/index.html'].links
    assert all('../' + path(d) in index_links for d in data['documents'])
    return {'source_records': 31, 'source_hashes': 'PASS', 'metadata': 'PASS', 'relationships': 'PASS', 'privacy_patterns': 'PASS'}
