from types import SimpleNamespace as NS
import pytest
from understanding.declaration_delta import apply_delta


def edit(quote, operation='ADD', target=None, kind='FACT'):
    return dict(operation=operation, kind=kind, quote=quote, target_id=target)


def delta(*edits, version=0):
    return dict(subject_id='example', expected_version=version, edits=list(edits))


def previous(result):
    return NS(version=1, subject_id='example', context={
        'declaration_contract': result['contract'], 'declarations': result['declarations']})


def test_add_preserves_unrelated_source_and_scope():
    first=apply_delta(None,delta(edit('The door is open.')),text='The door is open.',source_reference='message:1')
    out=apply_delta(previous(first),delta(edit('Nobody is visible.'),version=1),text='Nobody is visible.',source_reference='message:2')
    assert [v['quote'] for v in out['declarations']]==['The door is open.','Nobody is visible.']
    assert not out['execution_authority'] and not out['external_truth_confirmed']


def test_explicit_correction_preserves_lineage():
    first=apply_delta(None,delta(edit('Use XML.',kind='REQUIREMENT')),text='Use XML.',source_reference='message:1')
    target=first['declarations'][0]['id']
    out=apply_delta(previous(first),delta(edit('Use JSON.','REPLACE',target,'REQUIREMENT'),version=1),
                    text='Replace "Use XML." with "Use JSON."',source_reference='message:2')
    assert [v['quote'] for v in out['declarations']]==['Use JSON.']
    assert out['amendments'][0]['prior']['source_references']==['message:1']


def test_duplicate_is_not_multiplied():
    out=apply_delta(None,delta(edit('A is present.'),edit('A is present.')),text='A is present.',source_reference='message:1')
    assert len(out['declarations'])==1


@pytest.mark.parametrize('change',[
    delta(edit('Invented assertion.')),delta(edit('A is present.'),version=1),
    delta(edit('A is present.','REVOKE','unknown')),delta(edit('A is present.',kind='CONFIRMED'))])
def test_malformed_source_lineage_and_states_fail_closed(change):
    with pytest.raises(ValueError):apply_delta(None,change,text='A is present.',source_reference='message:1')


def test_delta_commits_through_existing_custody_and_store(tmp_path):
    from understanding import UnderstandingEngine, UnderstandingRequest, AuthorityContext, AuthorityLevel
    from understanding.understanding_store import UnderstandingStore
    engine=UnderstandingEngine(store=UnderstandingStore(tmp_path/'meaning.sqlite3'))
    def request(text, changes):
        return UnderstandingRequest(operator_id='op',thread_id='t',current_input=text,declaration_delta=changes,
            authority_context=AuthorityContext('op',AuthorityLevel.DIRECT_OPERATOR_STATEMENT,'OPERATOR',authenticated=True),
            runtime_metadata={'operator_source_reference':'message:'+str(changes['expected_version'])})
    first=engine.process(request('A is present.',delta(edit('A is present.'))))
    assert not first.errors and first.final_understanding is not None, first.to_dict()
    second=engine.process(request('B is absent.',delta(edit('B is absent.'),version=1)))
    assert not second.errors and second.final_understanding.version==2, second.to_dict()
    assert len(second.final_understanding.context['declarations'])==2
    assert second.governed_handoff()['execution_authority'] is False
    stale=engine.process(request('C is present.',delta(edit('C is present.'),version=1)))
    assert stale.errors
    assert engine.store.get('op',second.final_understanding.understanding_id).version==2


def test_contradiction_cannot_be_added_as_coauthoritative():
    first=apply_delta(None,delta(edit('A is present.')),text='A is present.',source_reference='message:1')
    with pytest.raises(ValueError,match='Contradictory'):
        apply_delta(previous(first),delta(edit('A is not present.'),version=1),text='A is not present.',source_reference='message:2')
