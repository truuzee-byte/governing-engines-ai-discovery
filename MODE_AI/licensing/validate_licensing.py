"""Validate this draft's mechanical scope and fixed business invariants.

Read-only unless --output is supplied. No contract activation or legal opinion.
Git blob hashes refer to repository bytes, independent of checkout line endings.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = '57c982b9aedd48983cc0eb2694ae9df2a8016805'
EDITABLE_EXISTING = {'README.md', 'MODE_AI/README.md', 'MODE_AI/CONTRIBUTING.md'}
CHECKS = []


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    CHECKS.append({'check': name, 'result': 'PASS'})


def original_tree():
    rows = {}
    for item in git('ls-tree', '-r', '-z', BASE).split(b'\0'):
        if not item:
            continue
        header, path = item.split(b'\t', 1)
        mode, kind, oid = header.decode().split()
        if kind != 'blob':
            raise AssertionError('Unexpected non-blob entry')
        rows[path.decode()] = oid
    return rows


def original_bodies(oids):
    proc = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    result = {}
    for oid in sorted(set(oids)):
        proc.stdin.write((oid + '\n').encode()); proc.stdin.flush()
        header = proc.stdout.readline().decode().split()
        assert len(header) == 3 and header[1] == 'blob'
        result[oid] = proc.stdout.read(int(header[2]))
        assert proc.stdout.read(1) == b'\n'
    proc.stdin.close(); assert proc.wait() == 0
    return result


def payment(attributable_revenue, allowable_attributable_expenses):
    # Synthetic amounts are already allocated, not a chosen allocation policy.
    return Decimal('0.01') * max(Decimal('0'), Decimal(attributable_revenue) - Decimal(allowable_attributable_expenses))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE / 'SCOPE_MANIFEST.json').read_text())
    schedule = json.loads((HERE / 'ACTIVATION_SCHEDULE.json').read_text())
    text = (HERE.parent / 'MODE_SOURCE_LICENSE.md').read_text(encoding='utf-8')
    notice = (HERE.parent / 'ATTRIBUTION_NOTICE.md').read_text(encoding='utf-8')
    register = (HERE / 'UNRESOLVED_DETAILS.md').read_text(encoding='utf-8')
    base = original_tree()
    covered = manifest['covered_files']
    expected = {p for p in base if p.startswith('MODE_AI/') and not p.endswith('.md')}
    check('Immutable repository/branch/snapshot scope', manifest['repository'] == 'truuzee-byte/governing-engines-ai-discovery'
          and manifest['publication_branch'] == 'mode-ai-publication-20261026'
          and manifest['snapshot_commit'] == BASE and BASE in text)
    check('Exact unique original code/configuration membership',
          len(covered) == len({r['path'] for r in covered}) == manifest['file_count'] == 477
          and {r['path'] for r in covered} == expected)
    bodies = original_bodies([r['git_blob'] for r in covered])
    check('All original Git blobs and SHA-256 values verified', all(
        base[r['path']] == r['git_blob']
        and len(bodies[r['git_blob']]) == r['bytes']
        and hashlib.sha256(bodies[r['git_blob']]).hexdigest() == r['sha256'] for r in covered))
    changes = set(filter(None, git('diff', '--name-only', '-z', BASE).decode().split('\0')))
    untracked = set(filter(None, git('ls-files', '--others', '--exclude-standard', '-z').decode().split('\0')))
    check('No original MODE functional/source/configuration changes', not changes.intersection(expected))
    check('Repository changes limited to licensing artifacts and three entrypoint docs', changes | untracked <= EDITABLE_EXISTING | {
        p.relative_to(ROOT).as_posix() for p in HERE.rglob('*') if p.is_file()
    } | {'MODE_AI/MODE_SOURCE_LICENSE.md', 'MODE_AI/ATTRIBUTION_NOTICE.md', 'MODE_AI/LICENSING_README.md'})
    check('Correct creator/project attribution', all(name in text and name in notice for name in ('DeMarius J. Lawson', 'Governing Engines')))
    check('Exactly one-percent attributable-profit model retained', 'exactly 1% (one percent)' in text
          and 'Participation Payment = 0.01 × Attributable Net Profit' in text
          and schedule['participation_rate'] == '0.01' and schedule['company_equity_granted'] is False)
    check('Commercial permission, retained ownership and unrelated/private exclusions explicit', all(phrase in text for phrase in (
        'Commercial use is permitted', 'No ownership of original MODE intellectual property is transferred',
        'Licensee retains ownership of independently created contributions', 'private MODE development',
        'research corpus', 'unrelated revenue', 'third-party license', 'does not revoke a prior valid permission')))
    ids = {f'D{i:02d}' for i in range(1, 15)}
    check('Every material decision remains explicitly open and activation blocked',
          schedule['status'] == manifest['status'] == 'DRAFT_NOT_EFFECTIVE'
          and schedule['operator_approved'] is False and schedule['effective_date'] is None
          and set(schedule['decisions']) == ids
          and all(d['status'] == 'OPEN' and d['resolution'] is None for d in schedule['decisions'].values())
          and all(identity in register for identity in ids) and 'NOT EFFECTIVE' in text)
    cases = [('100', '40', '0.60'), ('100', '100', '0'), ('100', '120', '0'),
             ('0', '0', '0'), ('200', '120', '0.80'), ('123.45', '23.45', '1.0000')]
    check('Six synthetic allocated-profit arithmetic cases', all(payment(r, e) == Decimal(want) for r, e, want in cases))
    # An unrelated revenue amount is deliberately not an argument to the model.
    check('Unrelated business revenue does not enter synthetic royalty base', payment('200', '120') == Decimal('0.80'))
    new_docs = [HERE.parent / n for n in ('MODE_SOURCE_LICENSE.md', 'ATTRIBUTION_NOTICE.md', 'LICENSING_README.md')]
    new_docs += [HERE / 'UNRESOLVED_DETAILS.md', HERE / 'SCOPE_AND_COMPATIBILITY.md']
    broken = []
    for file in new_docs:
        for target in re.findall(r'\]\(([^)]+)\)', file.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#'):
                if not (file.parent / target.split('#')[0]).is_file():
                    broken.append((file.name, target))
    check('All new local documentation links resolve', not broken)
    check('Historical no-license publication notice preserved', 'MODE_AI/PUBLICATION_NOTES.md' not in changes)
    result = {'status': 'PASS_DRAFT_MECHANICAL_VALIDATION', 'exit_status': 0,
              'command': 'python MODE_AI/licensing/validate_licensing.py --output MODE_AI/licensing/VALIDATION_RESULTS.json',
              'activation_status': 'BLOCKED_PENDING_D01_D14',
              'snapshot_commit': BASE, 'covered_original_files': len(covered), 'checks': CHECKS,
              'synthetic_arithmetic_cases': len(cases),
              'limits': 'No legal enforceability, title, universal license compatibility, existing-recipient assent, runtime behavior or contract activation established.'}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'checks_passed': len(CHECKS),
                      'covered_files': len(covered), 'activation_status': result['activation_status']}))


if __name__ == '__main__':
    main()
