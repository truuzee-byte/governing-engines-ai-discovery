"""Explicit authoritative obligations; unsupported predicates remain unproven."""
import hashlib
import json

CLASSES = {
    'requirements': 'REQUIRED_STATE', 'constraints': 'GOVERNANCE',
    'invariants': 'REQUIRED_STATE', 'dependencies': 'REQUIRED_STATE',
    'completion_conditions': 'COMPLETION', 'completion_condition': 'COMPLETION',
    'prohibited_states': 'PROHIBITED_STATE', 'authority_requirements': 'GOVERNANCE',
    'authority_dependencies': 'GOVERNANCE', 'evidence_requirements': 'EVIDENCE',
    'receipt_requirements': 'RECEIPT',
}


def obligation_requirements(structure):
    items = []

    def add(source, value, kind, parent=None):
        encoded = json.dumps(value, sort_keys=True, default=str)
        identity = value.get('requirement_id') if isinstance(value, dict) else None
        identity = identity or hashlib.sha256((source + encoded).encode()).hexdigest()
        predicate = value if isinstance(value, str) else ''
        invalid = not isinstance(value, (str, dict))
        if isinstance(value, dict):
            predicate = value.get('completion_condition') or value.get('text', '')
            allowed = set(CLASSES) | {'requirement_id', 'text', 'kind', 'source_references', 'justification'}
            invalid = (bool(set(value) - allowed) or
                       value.get('kind', 'REQUIREMENT') not in {'REQUIREMENT', 'CONSTRAINT', 'INVARIANT', 'DERIVED'} or
                       ('requirement_id' in value and (not isinstance(value['requirement_id'], str) or not value['requirement_id'])) or
                       any(key in value and not isinstance(value[key], str)
                           for key in ('text', 'completion_condition', 'justification')))
        invalid = invalid or not isinstance(predicate, str) or not predicate.strip()
        record = {'id': identity, 'source': source, 'original': value,
                  'authority_class': 'AUTHORITATIVE', 'obligation_class': kind,
                  'polarity': 'NEGATIVE' if kind == 'PROHIBITED_STATE' else 'POSITIVE',
                  'parent_id': parent, 'predicate': predicate if isinstance(predicate, str) else '',
                  'unresolved': invalid}
        items.append('obligation:' + json.dumps(record, sort_keys=True))
        if isinstance(value, dict):
            # The primary condition above retains the requirement identity. Other
            # nested governed groups have independent identities and checks.
            for key in CLASSES:
                if key in value and key != 'completion_condition':
                    group(source + '.' + key, value[key], CLASSES[key], identity)

    def group(source, values, kind, parent=None):
        if not isinstance(values, (list, tuple)):
            add(source, {'malformed_group': values}, kind, parent)
            return
        for index, value in enumerate(values):
            add(source + '[' + str(index) + ']', value, kind, parent)

    state = structure.get('understanding_requirements', {})
    for key, kind in CLASSES.items():
        if key in state:
            group('understanding_requirements.' + key, state[key], kind)
    for edge in structure.get('system_relationships', []):
        for key, kind in CLASSES.items():
            if key in edge:
                group('relationship:' + edge['relationship_id'] + '.' + key, edge[key], kind)
    for mechanism in structure.get('mechanism_requirements', {}).get('mechanism_requirements', []):
        add('mechanism:' + mechanism['mechanism_id'], mechanism, 'REQUIRED_STATE')
    return list(dict.fromkeys(items))
