"""Validate the final proposal's scope and operator-authorized business terms.

Read-only unless --output is supplied. No contract activation or legal opinion.
Git blob hashes refer to repository bytes, independent of checkout line endings.
"""
import argparse
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


def validate_contract_text(text):
    required = [
        "Governing Engines LLC is entitled to exactly 1% of each Covered Commercial Product's total net profit",
        'No estimated MODE contribution percentage, feature-level allocation, code-value fraction or similar discount',
        'All royalty payments are payable to Governing Engines LLC',
        'Developers must contact DeMarius J. Lawson to establish approved payment instructions before their first payment deadline',
        'Failure to initiate contact does not waive, suspend or extend',
        'consistent accrual accounting', 'five years after the end of the relevant quarter',
        '30 calendar days after receipt of notice to cure', 'AS IS. NO UPDATES PROMISED.',
        'no entitlement to future MODE versions, private MODE code, future Learning capabilities, upgrades, patches, support, maintenance or technical assistance',
        'no obligation to continue development or provide improvements',
        'does not revoke prior valid permissions', 'NOT EFFECTIVE',
        'No upfront licensing fee, minimum royalty or mandatory annual fee',
        'Ohio state courts or federal courts located in Ohio', 'no mandatory arbitration',
    ]
    for phrase in required:
        if phrase.casefold() not in text.casefold():
            raise AssertionError('Missing required contract provision: ' + phrase)
    for quarter, due in [('Q1', 'April 30 of the same year'), ('Q2', 'July 30 of the same year'),
                         ('Q3', 'October 30 of the same year'), ('Q4', 'January 30 of the following year')]:
        if not re.search(r'\| ' + quarter + r' \| [^\n]+ \| ' + due + r' \|', text):
            raise AssertionError('Incorrect contract quarter deadline: ' + quarter)
    for forbidden in ('Attributable Revenue', 'economically attributable to its covered code use',
                      'Attributable Net Profit =', 'D01–D14 remain OPEN'):
        if forbidden.casefold() in text.casefold():
            raise AssertionError('Obsolete contribution-based/open-decisions provision')


def main():
    import unittest
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        args.output.write_text('{"status":"RUNNING_NOT_YET_VERIFIED"}\n', encoding='utf-8')
    manifest = json.loads((HERE / 'SCOPE_MANIFEST.json').read_text(encoding='utf-8'))
    schedule = json.loads((HERE / 'ACTIVATION_SCHEDULE.json').read_text(encoding='utf-8'))
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
    check('Changes limited to licensing, entrypoint docs and CI validation', changes | untracked <= EDITABLE_EXISTING | {
        p.relative_to(ROOT).as_posix() for p in HERE.rglob('*') if p.is_file()
    } | {'MODE_AI/MODE_SOURCE_LICENSE.md', 'MODE_AI/ATTRIBUTION_NOTICE.md', 'MODE_AI/LICENSING_README.md', '.github/workflows/pages.yml'})
    index = {}
    for entry in git('ls-files', '--stage', '-z').split(b'\0'):
        if entry:
            header, name = entry.split(b'\t', 1)
            index[name.decode()] = header.decode().split()[1]
    check('All 477 current index blobs still equal frozen originals', all(index[p] == base[p] for p in expected))
    check('Creator/project attribution preserved', all(name in text and name in notice for name in ('DeMarius J. Lawson', 'Governing Engines')))
    validate_contract_text(text)
    check('Correct whole-product royalty, coordination, dates, no-updates and enforcement clauses', True)
    check('Single one-percent total-product model; no contribution or unrelated-company base',
          schedule['participation_rate'] == '0.01' and schedule['contribution_discount_allowed'] is False
          and schedule['unrelated_product_or_company_wide_royalty'] is False
          and schedule['company_equity_granted'] is False)
    check('LLC payee and creator coordination without invented banking/contact endpoint',
          schedule['payment_recipient'] == schedule['royalty_entitled_party'] == 'Governing Engines LLC'
          and schedule['payment_contact'] == 'DeMarius J. Lawson'
          and schedule['contact_required_before_first_payment_deadline'] is True
          and schedule['failure_to_contact_waives_or_extends_obligation'] is False
          and schedule['payment_instructions'] is None and schedule['reporting_channel'] is None)
    check('Quarterly accrual USD statements, same-product loss carryforward, no fees',
          schedule['accounting_basis'] == 'consistent accrual' and schedule['currency'] == 'USD'
          and schedule['zero_profit_statement_required'] is True
          and schedule['same_product_operating_loss_carryforward'] is True
          and schedule['cross_product_loss_offset'] is False
          and all(schedule[k] == '0' for k in ('upfront_fee','minimum_royalty','mandatory_annual_fee')))
    resolved = [k for k,v in schedule['decisions'].items() if v['status'] == 'RESOLVED']
    partial = [k for k,v in schedule['decisions'].items() if v['status'] == 'PARTIALLY_RESOLVED']
    check('Twelve resolved decisions; only title/third-party evidence remains partial',
          len(resolved) == 12 and set(partial) == {'D01','D12'}
          and all(v['resolved_on'] == '2026-10-31' and v['clauses'] for v in schedule['decisions'].values())
          and '12 decisions RESOLVED' in register and set(schedule['remaining_evidence']) == {'E01','E02'})
    check('No false activation, owner assignment, recipient assent or private implementation grant',
          schedule['status'] == manifest['status'] == 'FINAL_PROPOSAL_NOT_EFFECTIVE'
          and schedule['license_activation_approved'] is False
          and schedule['effective_date'] is None and schedule['acceptance_evidence'] is None
          and schedule['copyright_owner_legal_identity'] is None
          and 'no copyright assignment' in text.casefold()
          and 'no retroactive acceptance' in text.casefold()
          and 'private/current/future MODE code' in text)
    protected_docs = {p for p in base if p.startswith('MODE_AI/') and p.endswith('.md')} - {'MODE_AI/README.md','MODE_AI/CONTRIBUTING.md'}
    check('All pre-existing third-party/contract/publication documentation notices intact',
          not changes.intersection(protected_docs) and all(index[p] == base[p] for p in protected_docs))
    metadata_path = 'MODE_AI/licensing/THIRD_PARTY_METADATA.json'
    prior_metadata = git('rev-parse', '00da19ae4e2b5477aff7423e958677dd15119aca:' + metadata_path).decode().strip()
    check('Prior third-party license metadata evidence preserved',
          index[metadata_path] == prior_metadata
          and not git('diff', '--name-only', '00da19ae4e2b5477aff7423e958677dd15119aca', '--', metadata_path).strip())
    new_docs = [HERE.parent / n for n in ('MODE_SOURCE_LICENSE.md', 'ATTRIBUTION_NOTICE.md', 'LICENSING_README.md')]
    new_docs += [HERE / 'UNRESOLVED_DETAILS.md', HERE / 'SCOPE_AND_COMPATIBILITY.md']
    broken = []
    for file in new_docs:
        for target in re.findall(r'\]\(([^)]+)\)', file.read_text(encoding='utf-8')):
            if '://' not in target and not target.startswith('#') and not (file.parent / target.split('#')[0]).is_file():
                broken.append((file.name, target))
    check('All licensing documentation links resolve', not broken)
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern='test_licensing.py')
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    check('Licensing regression suite passed', outcome.wasSuccessful())
    result = {'status':'PASS_FINAL_PROPOSAL_VALIDATION','exit_status':0,
              'command':'python MODE_AI/licensing/validate_licensing.py --output MODE_AI/licensing/VALIDATION_RESULTS.json',
              'activation_status':'NOT_ACTIVATED; external rights evidence and release/assent gates remain',
              'snapshot_commit':BASE,'covered_original_files':len(covered),'checks':CHECKS,
              'regression_tests_run':outcome.testsRun,'resolved_decisions':len(resolved),'partially_resolved_evidence_items':partial,
              'limits':'No title, third-party authority, enforceability, actual acceptance, deployment or MODE runtime qualification is established.'}
    if args.output:
        args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ('status','covered_original_files','regression_tests_run','resolved_decisions')}))


if __name__ == '__main__':
    main()
