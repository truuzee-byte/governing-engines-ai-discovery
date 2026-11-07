"""Source-bound edits to operator-declared meaning, not claims of external truth.

The interpreter proposes edits. This boundary checks literal source custody and
the current version before deriving a candidate for the existing custody engine.
It neither writes records nor grants construction or Reality Primacy authority.
"""
from copy import deepcopy
import re
from .understanding_record import digest

KINDS = {'FACT', 'REQUIREMENT', 'CONSTRAINT', 'UNRESOLVED'}


def apply_delta(previous, delta, *, text, source_reference):
    if type(delta) is not dict or set(delta) != {'subject_id', 'expected_version', 'edits'}:
        raise ValueError('Malformed declaration delta')
    if not isinstance(delta['subject_id'], str) or not delta['subject_id'].strip():
        raise ValueError('Subject required')
    if type(delta['expected_version']) is not int or delta['expected_version'] != (previous.version if previous else 0):
        raise ValueError('Stale declaration version')
    if previous and previous.subject_id != delta['subject_id']:
        raise ValueError('Declaration subject mismatch')
    if not isinstance(source_reference, str) or not source_reference:
        raise ValueError('Source reference required')
    if type(text) is not str or not text.strip():
        raise ValueError('Operator statement required')
    if type(delta['edits']) is not list or not delta['edits']:
        raise ValueError('Explicit edits required')
    prior = deepcopy(previous.context.get('declarations', [])) if previous else []
    if previous and previous.context.get('declaration_contract') != 'OperatorDeclarations/1':
        raise ValueError('Cannot rewrite unrelated Understanding')
    current = {item['id']: item for item in prior}
    history = []
    for edit in delta['edits']:
        if type(edit) is not dict or set(edit) != {'operation', 'kind', 'quote', 'target_id'}:
            raise ValueError('Malformed declaration edit')
        operation, kind, quote, target = (edit[k] for k in ('operation', 'kind', 'quote', 'target_id'))
        if operation not in {'ADD', 'REPLACE', 'REVOKE'} or kind not in KINDS:
            raise ValueError('Unknown declaration operation/kind')
        if not isinstance(quote, str) or not quote.strip() or quote not in text:
            raise ValueError('Declaration must retain an exact operator source span')
        # Literal substring custody is necessary, but insufficient: selecting
        # only a consequent can erase an operator's condition; a fragment of a
        # question can look like an instruction. Refuse those lossy proposals.
        start=text.find(quote);end=start+len(quote)
        clause_start=max(text.rfind('\n',0,start),text.rfind('.',0,start),text.rfind('?',0,start),text.rfind('!',0,start))+1
        # If the source span already includes its sentence terminator, retain
        # that boundary instead of searching past it into the next sentence.
        # A partial consequent still searches forward for its own condition.
        boundary_end=start+len(quote.rstrip(' \t\r'))
        stop_start=boundary_end-1 if text[boundary_end-1] in '\n.?!' else end
        stops=[n for n in (text.find('\n',stop_start),text.find('.',stop_start),text.find('?',stop_start),text.find('!',stop_start)) if n>=0]
        clause=text[clause_start:min(stops)+1 if stops else len(text)].strip()
        if clause.endswith('?') and kind!='UNRESOLVED':
            raise ValueError('A question cannot become a declared fact or execution commitment')
        conditional=re.search(r'\b(?:if|unless|provided that|only when|only after|on condition that)\b',clause,re.I)
        if conditional and not re.search(r'\b(?:if|unless|provided that|only when|only after|on condition that)\b',quote,re.I):
            raise ValueError('Declaration omitted a material operator condition')
        if operation == 'ADD':
            if target is not None:
                raise ValueError('ADD cannot remove prior meaning')
        else:
            if target not in current:
                raise ValueError('Missing or already changed target')
            # A model's selection of a target is not authority to erase it.
            # Require the old text explicitly quoted by the operator alongside
            # a correction/revocation instruction. Ambiguous shorthand remains
            # unresolved rather than silently deleting unrelated meaning.
            old = current[target]
            explicit_intent = re.search(r'\b(?:correct|correction|replace|revoke|withdraw|instead of)\b', text, re.I)
            # A narrowly expressed expansion can replace a single exclusive
            # output declaration without requiring the operator to retype it.
            # Never use this exception to remove prohibitions or permissions.
            exclusive = [item for item in current.values() if re.match(
                r'^(?:it|this|the \w+)\s+only\s+(?:makes|produces|outputs|returns)\b', item['quote'], re.I)]
            expansion = (operation == 'REPLACE' and explicit_intent and len(exclusive) == 1
                         and exclusive[0]['id'] == target
                         and re.match(r'^(?:it|this|the \w+)\s+(?:can\s+)?also\s+(?:make|produce|output|return)\b', quote, re.I))
            if not explicit_intent or (old['quote'] not in text and not expansion):
                raise ValueError('Unbound correction: explicit prior text and edit intent required')
            history.append({'operation': operation, 'prior': current.pop(target), 'source_reference': source_reference})
            if expansion:
                # Remove exclusivity, not the previously declared output.
                # The retained predicate remains an exact span of its original
                # source; bind its subject through this same record.
                retained = re.split(r'\bonly\s+', old['quote'], maxsplit=1, flags=re.I)[1]
                retained_id = 'declaration:' + digest([delta['subject_id'], old['kind'], retained])[:24]
                current[retained_id] = {'id': retained_id, 'kind': old['kind'], 'quote': retained,
                                       'source_references': list(old['source_references']),
                                       'refinement_source_reference': source_reference}
        if operation != 'REVOKE':
            def unsigned(value):
                value = value.lower().replace("didn't", 'did not').replace("isn't", 'is not').replace("can't", 'can not')
                return re.sub(r'\s+', ' ', value.replace(' not ', ' ')).strip()
            for prior_item in current.values():
                if (re.match(r'^(?:it|this|the \w+)\s+only\s+(?:makes|produces|outputs|returns)\b', prior_item['quote'], re.I)
                        and re.match(r'^(?:it|this|the \w+)\s+(?:can\s+)?also\s+(?:make|produce|output|return)\b', quote, re.I)):
                    raise ValueError('Exclusive output declaration requires explicit replacement, not additive confirmation')
                if unsigned(prior_item['quote']) == unsigned(quote) and prior_item['quote'].lower() != quote.lower():
                    raise ValueError('Contradictory declaration requires explicit correction')
            identity = 'declaration:' + digest([delta['subject_id'], kind, quote])[:24]
            if identity in current:
                current[identity]['source_references'] = sorted(set(current[identity]['source_references'] + [source_reference]))
            else:
                current[identity] = {'id': identity, 'kind': kind, 'quote': quote,
                                     'source_references': [source_reference]}
    items = list(current.values())
    return {'contract': 'OperatorDeclarations/1', 'subject_id': delta['subject_id'],
            'expected_version': delta['expected_version'], 'declarations': items,
            'amendments': history, 'source_reference': source_reference,
            'meaning': 'The operator declared:\n' + '\n'.join(item['quote'] for item in items),
            'execution_authority': False, 'external_truth_confirmed': False}
