"""Reuse Understanding's structural engines; recognition grants no authority."""
from dataclasses import asdict
from understanding.chain_recognition_engine import ChainRecognitionEngine
from understanding.chain_relationship_mapper import ChainRelationshipMapper
from understanding.mechanism_derivation_engine import MechanismDerivationEngine
from understanding.decomposition_engine import DecompositionEngine
from understanding.system_relationship import SystemRelationship, RelationshipType
from understanding.system_chain import ChainType
from ..contracts import digest
import json


def analyze(capability):
    edges = []
    for raw in capability.chain_relationships:
        raw = dict(raw)
        raw['relationship_type'] = RelationshipType(raw['relationship_type'])
        edge = SystemRelationship(**raw)
        if edge.operator_id != capability.operator_id or edge.system_id != capability.capability_id:
            raise PermissionError('Relationship ownership mismatch')
        edges.append(edge)
    recognition = ChainRecognitionEngine().recognize(edges, capability.purpose, capability.required_chains)
    mapping = ChainRelationshipMapper().map(recognition, edges)
    decomposition = DecompositionEngine().decompose(capability.capability_id, edges)
    mechanisms = MechanismDerivationEngine().derive(edges, recognition, decomposition)
    unresolved = list(recognition.unresolved_questions) + list(mapping.unresolved_conflicts)
    unresolved.extend(g.description for g in mechanisms.structural_gaps if g.gap_type == 'UNRESOLVED_JUSTIFICATION')
    if not recognition.chain_records:
        unresolved.append('No justified required chain')
    declared = {m.get('mechanism_id') for m in capability.mechanisms}
    required = {m.mechanism_id for m in mechanisms.mechanism_requirements}
    if declared != required:
        unresolved.append('Derived mechanism set differs from capability declaration')
    definitions = {m.mechanism_id: asdict(m) for m in mechanisms.mechanism_requirements}
    for mechanism in capability.mechanisms:
        defined = {k: v for k, v in mechanism.items() if k != 'completion_requirements'}
        if digest(defined) != digest(definitions.get(mechanism.get('mechanism_id'))):
            unresolved.append('Declared mechanism changes its derived structural obligations')
    return {'recognition': asdict(recognition), 'relationships': asdict(mapping),
        'derivation': asdict(mechanisms), 'unresolved': unresolved,
        'status': 'UNPROVEN' if unresolved else 'STRUCTURALLY_DEFINED',
        'capability_proven': False,
        'precedence': ['Reality constrains Learning', 'Authority constrains modification',
                       'Continuity constrains transformation', 'Preservation laws constrain execution']}


KERNEL_CHAINS = tuple(c.value for c in ChainType)


def build_obligations(capability):
    """Lossless structural identity attached to each existing Builder predicate."""
    result = []
    for mechanism in capability.mechanisms:
        for predicate in mechanism.get('completion_requirements', []):
            obligation = {'id': digest([capability.capability_id, mechanism, predicate]),
                'source': 'SystemLayer/1:' + capability.capability_id,
                'original': {'mechanism': mechanism, 'required_chains': capability.required_chains,
                    'chain_relationships': capability.chain_relationships, 'invariants': capability.invariants,
                    'capability_declaration': capability.declaration()},
                'authority_class': 'AUTHORITATIVE', 'obligation_class': 'COMPLETION',
                'polarity': 'POSITIVE', 'predicate': predicate, 'unresolved': False}
            result.append('obligation:' + json.dumps(obligation, sort_keys=True))
    for predicate in capability.prohibited_behavior:
        obligation = {'id': digest([capability.capability_id, 'prohibited', predicate]),
            'source': 'SystemLayer/1:' + capability.capability_id,
            'original': {'prohibited_behavior': predicate, 'capability_declaration': capability.declaration()},
            'authority_class': 'AUTHORITATIVE', 'obligation_class': 'PROHIBITED_STATE',
            'polarity': 'NEGATIVE', 'predicate': predicate, 'unresolved': False}
        result.append('obligation:' + json.dumps(obligation, sort_keys=True))
    return result
