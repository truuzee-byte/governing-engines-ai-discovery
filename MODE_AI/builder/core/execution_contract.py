"""Executable checks for the existing BuildPlan. Unknown prose remains unproven.

Requirement strings remain unchanged. Supported exact predicates are documented
below; no inference from an unrelated successful command satisfies free text.
"""
import json
import hashlib
from pathlib import Path


def contained(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Expected a relative artifact path")
    if ".." in Path(relative).parts or ":" in relative:
        raise ValueError("Path traversal or alternate stream denied")
    target = (root / relative).resolve()
    target.relative_to(root)
    if target == root:
        raise ValueError("File path cannot be the artifact root")
    return target


def validate_target(plan, artifact_root):
    target = Path(plan.repository_target)
    root = Path(artifact_root)
    if not plan.repository_target or not target.is_absolute() or not root.is_absolute():
        raise ValueError("Canonical repository target and artifact root must be absolute paths")
    # Exact root binding: scopes are relative to this canonical directory.
    if target.resolve() != root.resolve():
        raise ValueError("artifact_root does not match canonical repository_target")
    for value in (plan.required_files + plan.required_directories + plan.required_outputs
                  + plan.authorized_create_scope + plan.authorized_write_scope):
        contained(root.resolve(), value)


def validate_operations(proposals, artifact_root):
    root = Path(artifact_root).resolve()
    for item in proposals:
        target = contained(root, item.path)
        if item.operation == "CREATE":
            if target.exists() or target.is_symlink():
                raise ValueError(f"CREATE target already exists: {item.path}")
        elif item.operation == "MODIFY":
            if not target.is_file():
                raise ValueError(f"MODIFY target does not exist: {item.path}")
        else:
            raise ValueError(f"Unsupported operation: {item.operation}")


def check_success_requirements(plan, artifact_root, commands):
    root = Path(artifact_root).resolve()
    results = []

    def record(group, requirement, passed, reason):
        kind = {'completion': 'COMPLETION', 'evidence': 'EVIDENCE',
                'governance': 'GOVERNANCE', 'receipt': 'RECEIPT'}.get(group, 'REQUIRED_STATE')
        source = 'build_plan.' + {'validation': 'validation_requirements', 'completion': 'completion_requirements',
            'evidence': 'evidence_requirements', 'governance': 'governance_constraints',
            'receipt': 'receipt_requirements'}.get(group, group)
        results.append({"validation_type": "success_requirement", "group": group,
                        "requirement": requirement, "executed": True,
                        "contract_obligation": {
                            'id': hashlib.sha256((source + json.dumps(requirement, sort_keys=True)).encode()).hexdigest(),
                            'source': source, 'original': requirement, 'authority_class': 'AUTHORITATIVE',
                            'obligation_class': kind, 'polarity': 'POSITIVE'},
                        "state": "PASSED" if passed else "UNPROVEN", "reason": reason})

    for group, paths, directory in (("required_files", plan.required_files, False),
            ("required_directories", plan.required_directories, True),
            ("required_outputs", plan.required_outputs, False)):
        for path in paths:
            target = contained(root, path)
            present = target.is_dir() if directory else target.is_file()
            record(group, path, present, "Present" if present else "Required artifact missing")

    for group, requirements in (("validation", plan.validation_requirements),
            ("evidence", plan.evidence_requirements), ("completion", plan.completion_requirements),
            ("governance", plan.governance_constraints), ("receipt", plan.receipt_requirements)):
        for requirement in requirements:
            original_requirement = requirement
            if group == 'receipt' and requirement == 'build_receipt':
                requirement = 'receipt written'
            obligation = None
            if requirement.startswith('obligation:'):
                obligation = json.loads(requirement[len('obligation:'):])
                requirement = obligation['predicate']
            passed = False
            if requirement in {"validation commands passed", "required_validation_must_execute"}:
                passed = bool(plan.validation_commands) and all(any(
                    r.get("command") == cmd and r.get("returncode") == 0 for r in commands)
                    for cmd in plan.validation_commands)
            elif requirement == "command results":
                passed = bool(commands) and all("returncode" in r for r in commands)
            elif requirement == "approved file contents match":
                passed = bool(plan.approved_files) and all(contained(root, p).is_file() and
                    contained(root, p).read_text(encoding="utf-8") == text
                    for p, text in plan.approved_files.items())
            elif requirement.startswith("file:"):
                passed = contained(root, requirement[5:]).is_file()
            elif requirement.startswith("command:"):
                try:
                    cmd = json.loads(requirement[8:])
                    passed = cmd in plan.validation_commands and any(
                        r.get("command") == cmd and r.get("returncode") == 0 for r in commands)
                except (ValueError, TypeError):
                    pass
            record(group, requirement, passed,
                   "Predicate established" if passed else "Required proof missing or predicate unsupported")
            results[-1]['contract_obligation']['original'] = original_requirement
            if obligation is not None:
                results[-1]['obligation'] = obligation
                results[-1]['contract_obligation'] = obligation
                if obligation.get('unresolved') or obligation.get('polarity') not in {'POSITIVE', 'NEGATIVE'}:
                    results[-1].update(state='UNPROVEN', reason='Malformed or unsupported authoritative obligation')
                elif obligation['polarity'] == 'NEGATIVE':
                    # Only a supported absence check can establish a prohibition.
                    # Failure to interpret a predicate is never proof of absence.
                    if requirement.startswith('file:'):
                        contained(root, requirement[5:])
                        target = root / requirement[5:]
                        try:
                            target.lstat()
                        except FileNotFoundError:
                            results[-1].update(state='PASSED', reason='Prohibited path absent')
                        except OSError:
                            results[-1].update(state='UNPROVEN', reason='Cannot establish prohibited path absence')
                        else:
                            results[-1].update(state='FAILED', reason='Prohibited path present')
                    else:
                        results[-1].update(state='UNPROVEN', reason='Unsupported prohibited expression')
            if (requirement == "approved file contents match" and plan.approved_files and not passed
                    and all(contained(root, p).is_file() for p in plan.approved_files)):
                results[-1].update(state="FAILED", reason="Observed contents differ from approved contents")
    return results
