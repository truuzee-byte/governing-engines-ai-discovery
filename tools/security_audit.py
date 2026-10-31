"""Read-only content inventory of explicit Git refs and every reachable historical blob.

Outputs paths, object identities and pattern locations, never matched values.
This is static triage, not a credential validity check or an IP release decision.
"""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

PATTERNS = {
    'credential_format': r'\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{25,}|AKIA[A-Z0-9]{16})\b|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
    'credential_assignment': r'(?i)(?:api_key|password|secret|token)\s*[=:]\s*[\x22\x27][^\x22\x27\r\n]{8,}[\x22\x27]',
    'personal_or_local': r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b[A-Za-z]:[\\/][^\s<>\x22]+',
    'private_boundary': r'(?i)internal.only|confidential|private (?:agreement|source|attachment)|revenue.shar|intellectual.property assignment',
    'runtime_evidence': r'(?i)\.jsonl|provider_response|traceback|runtime_traces|raw_input',
    'mechanism': r'(?i)threshold|weights|authority|governance|memory|learning|scoring',
}


def git(*args):
    return subprocess.check_output(['git', *args])


def tree(ref):
    result = []
    for row in git('ls-tree', '-r', '-z', ref).split(b'\0'):
        if not row:
            continue
        header, name = row.split(b'\t', 1)
        mode, kind, oid = header.decode().split()
        result.append({'path': name.decode('utf-8'), 'mode': mode, 'kind': kind, 'oid': oid})
    return result


def blobs(oids):
    # One process; read exact sizes so binary contents cannot corrupt framing.
    proc = subprocess.Popen(['git', 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    result = {}
    for oid in sorted(oids):
        proc.stdin.write((oid + '\n').encode()); proc.stdin.flush()
        header = proc.stdout.readline().decode().split()
        if len(header) != 3 or header[1] != 'blob':
            raise ValueError('Unreadable Git blob: ' + oid)
        body = proc.stdout.read(int(header[2])); assert proc.stdout.read(1) == b'\n'
        result[oid] = body
    proc.stdin.close(); assert proc.wait() == 0
    return result


def classify(path, text):
    if path == '.github/workflows/pages.yml':
        return 'HOLD', 'F', 'Actions use mutable major-version tags rather than immutable SHAs. Recommend approved SHA pins. Separately verified Pages environment allows main only.'
    if path.startswith('MODE_AI/'):
        if path.endswith('supervisor_bridge/api.py'):
            return 'HOLD', 'A/F', 'WebSocket bearer token is accepted in the URL query; URL logging by intermediaries can expose it. No deployed instance or actual exposed token established.'
        if path.endswith(('requirements-bridge.txt', 'requirements.txt', 'requirements-media.txt', 'requirements-test.txt')):
            return 'HOLD', 'F', 'Runtime dependencies lack a complete hash-locked transitive resolution; optional bridge dependencies are unpinned. Advisory coverage is reported separately.'
        if '/tests/' in path and re.search(r'C:[/\\]MODE_AI[/\\]artifacts', text):
            return 'HOLD', 'D', 'Contains references to excluded private historical qualification artifacts. Payloads are absent; operator should approve disclosure of the evidence naming/lineage.'
        detailed_contract = any(path.endswith(p) for p in (
            'learning/CONTRACT.md', 'learning/canonical.py', 'learning/service.py',
            'learning/corrective.py', 'learning/relationships.py', 'learning/revalidation_sources.py',
            'learning/architecture_changes.py', 'learning/runtime.py',
            'data_governance/context_admission.py', 'data_governance/learning_governance.py',
            'data_governance/memory_governance.py', 'data_governance/response_gate.py',
            'data_governance/document_admission.py', 'data_governance/material_admission.py',
            'persistent_memory/learning_gateway.py', 'builder/handoff/authority_checker.py',
            'builder/handoff/snapshot_verifier.py', 'builder/handoff/mode_to_builder_adapter.py',
            'builder/handoff/specification_receiver.py', 'integration/objective_action_rp.py',
            'integration/reality_primacy.py', 'integration/rp_evidence_state.py', 'specs/handoff_gate.py'))
        if (re.search(r'STRUCTURAL_WEIGHTS|ambiguity_score\s*>=|interpretation_stability_score\s*[<>]|operator_alignment_score\s*[<>]', text)
                or (detailed_contract and len(text.strip()) > 300)):
            return 'HOLD', 'C', 'Content discloses executable scoring, admission, authority or learned-memory enforcement contracts beyond ordinary public scaffolding. Proprietary status requires operator judgment; not a confirmed secret.'
        return 'ALREADY PUBLIC', None, 'Previously published implementation, tests or documentation; no specific disclosure removal established by this static review.'
    return 'ALREADY PUBLIC', None, 'Existing intentional publication/evidence/tooling; no specific removal established by content triage and targeted review.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refs', nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    commits = git('rev-list', *args.refs).decode().splitlines()
    objects = {}
    for commit in commits:
        for item in tree(commit):
            if item['kind'] != 'blob':
                raise ValueError('Non-blob tree entry requires separate inspection: ' + item['path'])
            entry = objects.setdefault(item['oid'], {'paths': set(), 'commits': set()})
            entry['paths'].add(item['path']); entry['commits'].add(commit)
    bodies = blobs(objects)
    history = []
    for oid, meta in sorted(objects.items()):
        body = bodies[oid]; text = body.decode('utf-8', errors='replace')
        matches = {name: [n for n, line in enumerate(text.splitlines(), 1) if re.search(pattern, line)] for name, pattern in PATTERNS.items()}
        syntax = None
        if any(p.endswith('.py') for p in meta['paths']):
            try:
                ast.parse(text.lstrip('\ufeff')); syntax = 'PASS'
            except SyntaxError:
                syntax = 'FAIL'
        history.append({'oid': oid, 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body),
                        'paths': sorted(meta['paths']), 'commits': sorted(meta['commits']),
                        'pattern_lines': matches, 'python_syntax': syntax})
    files = []
    for ref in args.refs:
        commit = git('rev-parse', ref).decode().strip()
        for item in tree(ref):
            text = bodies[item['oid']].decode('utf-8', errors='replace')
            classification, category, reason = classify(item['path'], text)
            files.append({**item, 'branch': ref, 'commit': commit, 'classification': classification,
                          'category': category, 'reason': reason,
                          'action': 'Request operator decision; retain pending approval' if classification == 'HOLD' else 'Retain',
                          'accessible_in_git_history': True,
                          'inspection': 'Entire blob content processed by static rules; targeted manual review described in audit report'})
    result = {'scope_refs': args.refs, 'reachable_commits': commits, 'historical_unique_blobs': len(history),
              'historical_bytes': sum(x['bytes'] for x in history),
              'classification_counts': dict(Counter(x['classification'] for x in files)),
              'files': files, 'historical_blobs': history,
              'limits': 'No runtime qualification, credential probing, private-document ownership inference or guarantee against unknown secrets. Binary visuals and new PDF reviewed separately.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('historical_unique_blobs', 'historical_bytes', 'classification_counts')}))
    assert not any(h['python_syntax'] == 'FAIL' for h in history), 'Historical Python syntax failure'


if __name__ == '__main__':
    main()
