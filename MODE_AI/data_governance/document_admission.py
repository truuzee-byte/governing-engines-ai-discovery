"""Reapply existing document contracts at import and hydration boundaries.

Approval is the existing operator-scoped, content-bound contract, not a claim
made by document text. This is not protection against hostile database owners.
"""
import json

# Process-local writer provenance; never serialized as authority.
_DOCUMENT_WRITER = object()


def validate_document(db, value, history):
    from .custody_store import CustodyStore
    from specs.document_service import DocumentService
    if value['namespace'] not in {'DOCUMENT', 'DOCUMENT_AUTHORITY'}:
        return

    class ValidationStore:
        def retrieve(self, namespace, owner, identity, *, version, expected_hash):
            records = (history if (namespace, owner, identity) ==
                (value['namespace'], value['owner'], value['object_id']) else
                CustodyStore._history(db, namespace, owner, identity))
            if type(version) is not int or not 1 <= version <= len(records):
                raise PermissionError('Document source lineage unavailable')
            source = records[version - 1]
            if source['record_hash'] != expected_hash:
                raise PermissionError('Document source hash mismatch')
            return source

        def append(self, namespace, owner, identity, content, metadata, *, expected_previous, authorization, document_admission=None):
            expected = (value['namespace'], value['owner'], value['object_id'],
                value['content'], value['metadata'], value['previous_hash'], value['authorization'])
            # Authority JSON whitespace is not authority; compare parsed content.
            actual = (namespace, owner, identity, content, metadata, expected_previous, authorization)
            if namespace == 'DOCUMENT_AUTHORITY':
                expected = (*expected[:3], json.loads(expected[3]), *expected[4:])
                actual = (*actual[:3], json.loads(actual[3]), *actual[4:])
            if actual != expected:
                raise PermissionError('Document import differs from governed contract')

    documents = object.__new__(DocumentService)
    documents.store = ValidationStore()
    owner, approval, metadata = value['owner'], value['authorization'], value['metadata']
    if value['namespace'] == 'DOCUMENT' and 'stage' in metadata:
        # Existing cinematic candidate writer retains its original operator
        # approval; do not fabricate a DOCUMENT_INTAKE approval for that action.
        from system_layer.contracts import authorize, digest
        request = metadata['derivation_request']
        if approval.get('action') not in {'CINEMATIC_INTERPRET','CINEMATIC_DERIVE','CINEMATIC_SPECIFY','CINEMATIC_REVIEW_CANDIDATE'}:
            raise PermissionError('Candidate derivation approval required')
        authorize(owner, approval['action'], request, approval)
        source = documents.retrieve(owner, **request['reference'])
        body = json.loads(value['content'])
        expected = dict(project_id=source['metadata']['project_id'],thread_id=metadata['thread_id'],
            kind='GENERATED_CANDIDATE',visual_authority='GENERATED_CANDIDATE',
            knowledge_class=source['metadata']['knowledge_class'],authority='DERIVED_FROM_SELECTED_AUTHORED_INTENT',
            source_reference=source['record_hash'],stage=metadata['stage'],derivation_request=request,
            claims_validated=False,execution_authority=False)
        if (metadata != expected or request['project_id'] != expected['project_id'] or
                not metadata['thread_id'] or source['metadata']['kind'] not in {'CANON','AUTHORITATIVE','SPECIFICATION'} or
                value['object_id'] != 'cinematic:'+metadata['stage']+':'+digest({'request':request,'value':body})):
            raise PermissionError('Derived candidate custody mismatch')
        return
    if value['namespace'] == 'DOCUMENT_AUTHORITY':
        from .custody_json import load
        from io import StringIO
        body = load(StringIO(value['content']))
        request = {k: v for k, v in body.items()
                   if k not in {'contract', 'claims_validated', 'execution_authority'}}
        documents.reconcile_authority(owner, request, approval)
        return
    if 'restoration_source' in metadata:
        documents.restore(owner, dict(source=metadata['restoration_source'],
            expected_previous=value['previous_hash'], reason=metadata['restoration_reason']), approval)
        return
    extras = {'derivation', 'derivation_sources', 'mechanism_reference',
              'claims_validated', 'rendered_output_observed'}
    request = dict(object_id=value['object_id'], content=value['content'],
                   expected_previous=value['previous_hash'],
                   **{k: v for k, v in metadata.items() if k not in extras})
    if 'derivation' in metadata:
        documents.derive(owner, dict(document=request,
            sources=[s['reference'] for s in metadata['derivation_sources']],
            derivation=metadata['derivation'], mechanism_reference=metadata['mechanism_reference']), approval)
    else:
        documents.intake(owner, request, approval)
