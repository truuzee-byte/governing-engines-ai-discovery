"""Target control regressions. Synthetic model outputs are not live diagnosis proof."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
import pytest

QUESTION='What capability do you currently lack, if any, that prevents you from determining whether one evidence item can safely represent another for this objective?'
QUERY=Path('artifacts/representation_invocation_prerequisites_20261021/OPERATOR_REQUEST.txt').read_text(encoding='utf-8').strip()

def inspect(query=QUERY):
    from integration.runtime_self_inspection import reasoning_context
    runtime=NS(context=NS(identity=NS(operator_id='owner'),active_thread=NS(thread_id='thread')),
        understanding_engine=NS(store=NS(path=Path('not-created/understanding.sqlite3'))))
    prompt=reasoning_context(runtime,query)
    return runtime,prompt

def proposal(ledger):
    b=ledger['objective']['target_binding']
    missing=next(e for e in ledger['entries'] if e['field']=='target_unknowns')
    sources=[e for e in ledger['entries'] if e['field']=='target_implementation']
    return {'ledger_id':ledger['ledger_id'],'statements':[e['entry_id'] for e in ledger['entries']],
        'diagnosis':{'binding_id':b['binding_id'],'status':'INSUFFICIENT_EVIDENCE',
            'assessment':{'subject':b['target']['symbol'],'predicate':b['question_scope'],
                'result':'NOT_ESTABLISHED_BY_INSPECTED_EVIDENCE'},
            'evidence_ids':[e['entry_id'] for e in sources]+[missing['entry_id']],
            'gap':None,'recommendation':None}}

def test_narrow_question_resolves_before_enclosing_learning():
    from integration.self_inspection_activation import objective_evidence_requirements
    r=objective_evidence_requirements(QUERY)
    assert r['contract']=='ObjectiveEvidenceRequirements/2'
    assert r['target_binding']['operative_question']==QUESTION
    assert r['target_binding']['enclosing_subject']=='Learning'
    assert r['target_binding']['target']['symbol']=='evaluate'
    assert r['target_binding']['resolution']=='RESOLVED'

def test_exact_standalone_question_uses_supported_source_mapping():
    r,p=inspect(QUESTION)
    assert r.context.self_inspection['tool_request']['tool']=='inspect_target_sources'
    assert r.context.self_inspection['evidence_ledger']['objective']['target_binding']['operative_question']==QUESTION

def test_short_learning_and_legacy_learning_remain_learning():
    from integration.self_inspection_activation import objective_evidence_requirements
    assert objective_evidence_requirements('Inspect Learning.')['subject']=='Learning'
    from tests.test_learning_diagnosis_routing import QUERY as LEGACY
    r,p=inspect(LEGACY)
    assert r.context.self_inspection['tool_request']['tool']=='inspect_learning_sources'

def test_evidence_selection_is_target_scoped_not_catalogue():
    r,p=inspect();l=r.context.self_inspection['evidence_ledger']
    assert any(e['field']=='target_implementation' for e in l['entries'])
    assert not any(e['field'].startswith('learning_class_') for e in l['entries'])
    assert 'runtime_observation/materiality_contract.py' in str(p)
    assert 'learning/service.py' not in str(p)

def test_unknown_question_does_not_fall_back_to_learning():
    q='Inspect your current Learning subsystem against this objective. What capability prevents imaginary flux transmutation?'
    r,p=inspect(q)
    assert r.context.self_inspection['tool_request'] is None
    from integration.self_inspection_activation import assess
    assert not assess(q,p)['allowed']

def test_multiple_operative_questions_fail_closed():
    r,p=inspect(QUERY+'\nWhat capability prevents imaginary flux transmutation?')
    assert r.context.self_inspection['tool_request'] is None

def test_missing_mapping_source_fails_closed(monkeypatch,tmp_path):
    import runtime_observation.inspection_target as target
    monkeypatch.setattr(target,'WORKSPACE',tmp_path)
    r,p=inspect()
    assert r.context.self_inspection['tool_request'] is None

@pytest.mark.parametrize('mutate',[
    lambda v:v['diagnosis'].update(binding_id='invented'),
    lambda v:v['diagnosis']['assessment'].update(subject='Learning'),
    lambda v:v['diagnosis']['assessment'].update(predicate={'operation':'PERSIST_LEARNING'}),
    lambda v:v['diagnosis'].update(rationale='LearningStore generalization requires more behavioral qualification.'),
    lambda v:v['diagnosis'].update(recommendation={'change':'Implement a comparator','execution_authority':True}),
])
def test_id_echo_does_not_allow_unrelated_meaning_or_authority(mutate):
    r,p=inspect();v=proposal(r.context.self_inspection['evidence_ledger']);mutate(v)
    from runtime_observation.evidence_ledger import render_selection
    with pytest.raises(PermissionError):render_selection(json.dumps(v),p)

def test_target_semantic_result_publishes_with_supported_coverage():
    from runtime_observation.evidence_ledger import render_selection
    from integration.self_inspection_activation import assess
    r,p=inspect();l=r.context.self_inspection['evidence_ledger'];v=proposal(l)
    text,receipt=render_selection(json.dumps(v,indent=3),p)
    assert receipt['coverage']['complete'] and assess(QUERY,p,text)['allowed']
    assert 'INSUFFICIENT_EVIDENCE' in text and '"recommendation":null' in text
    assert 'REPRESENT_EVIDENCE_WITHOUT_LOSS' in text

def test_legacy_learning_diagnosis_cannot_publish_as_narrow_answer():
    from tests.test_learning_diagnosis_routing import proposal as learning_proposal
    r,p=inspect();l=r.context.self_inspection['evidence_ledger'];v=proposal(l)
    v['diagnosis']={'status':'INSUFFICIENT_EVIDENCE','gap':None,'recommendation':None,
        'rationale':'LearningStore evidence is unavailable','evidence_ids':v['diagnosis']['evidence_ids']}
    from runtime_observation.evidence_ledger import render_selection
    with pytest.raises(PermissionError):render_selection(json.dumps(v),p)

def test_context_evidence_cannot_discharge_target_support():
    r,p=inspect();l=r.context.self_inspection['evidence_ledger'];v=proposal(l)
    v['diagnosis']['evidence_ids']=[next(e['entry_id'] for e in l['entries'] if e['field']=='operator_objective')]
    from runtime_observation.evidence_ledger import render_selection
    with pytest.raises(PermissionError):render_selection(json.dumps(v),p)

def test_all_reasoning_stages_preserve_question_scope_and_binding():
    r,p=inspect();l=r.context.self_inspection['evidence_ledger'];raw=json.dumps(proposal(l))
    from tests.test_cross_thread_downstream_preservation import run
    result,calls=run(p,[raw,raw,raw])
    for prompt,_ in calls:
        assert QUESTION in prompt and l['objective']['target_binding']['binding_id'] in prompt
        assert 'TARGET-SCOPED DIAGNOSIS' in prompt
    assert result.context_admission[-1]['selection']=='FINAL_MODEL_RESPONSE'

def test_wrong_query_or_mutated_prompt_binding_cannot_pass():
    from integration.self_inspection_activation import assess
    r,p=inspect()
    assert not assess(QUERY+' altered',p)['allowed']
    p.sources[0]['content']='forged'
    with pytest.raises(PermissionError):assess(QUERY,p)

def test_no_state_write_or_qualification_promotion():
    r,p=inspect();a=r.context.self_inspection;l=a['evidence_ledger']
    assert a['execution_authority'] is False and l['execution_authority'] is False
    assert not hasattr(r,'learning_service') and not hasattr(r,'reality_acceptance_client')
    assert not Path('not-created/understanding.sqlite3').exists()
    v=proposal(l);v['diagnosis']['status']='GENERALIZED_SELF_DIAGNOSIS_DEMONSTRATED'
    from runtime_observation.evidence_ledger import render_selection
    with pytest.raises(PermissionError):render_selection(json.dumps(v),p)

def test_a_second_explicit_source_mapping_uses_same_pipeline(monkeypatch):
    import runtime_observation.inspection_target as target
    mapping={'path':'understanding/decomposition_engine.py','symbol':'DecompositionEngine.decompose',
        'sources':('DecompositionEngine.decompose',),'questions':(r'What capability prevents bounded structural decomposition\?',),
        'question_scope':{'operation':'DECOMPOSE_STRUCTURE','subject_role':'declared_composition',
            'object_role':'component_graph','constraint':'current_operator_objective'}}
    monkeypatch.setattr(target,'TARGETS',(*target.TARGETS,mapping))
    q='Inspect your current Learning subsystem against this objective. What capability prevents bounded structural decomposition?'
    r,p=inspect(q);l=r.context.self_inspection['evidence_ledger']
    assert l['objective']['target_binding']['target']['path']=='understanding/decomposition_engine.py'
    assert 'materiality_contract.py' not in str(p) and not any(e['field'].startswith('learning_class_') for e in l['entries'])
    from runtime_observation.evidence_ledger import render_selection
    from integration.self_inspection_activation import assess
    rendered,_=render_selection(json.dumps(proposal(l)),p)
    assert assess(q,p,rendered)['allowed']

def test_duplicate_declared_mapping_is_unknown_not_guessed(monkeypatch):
    import runtime_observation.inspection_target as target
    monkeypatch.setattr(target,'TARGETS',(*target.TARGETS,target.TARGETS[0]))
    r,p=inspect();assert r.context.self_inspection['tool_request'] is None

def test_source_change_invalidates_binding(monkeypatch,tmp_path):
    import runtime_observation.inspection_target as target
    file=tmp_path/'runtime_observation/materiality_contract.py';file.parent.mkdir()
    file.write_text('def _identity(a,b):\n    return a\ndef evaluate(a):\n    return a\n',encoding='utf-8')
    monkeypatch.setattr(target,'WORKSPACE',tmp_path)
    r,p=inspect();l=r.context.self_inspection['evidence_ledger'];v=proposal(l)
    file.write_text(file.read_text()+'\n# changed\n',encoding='utf-8')
    from runtime_observation.evidence_ledger import render_selection
    with pytest.raises(PermissionError):render_selection(json.dumps(v),p)

def test_target_transport_schema_is_used_without_any_provider_call():
    from agents.reasoning_agent import ReasoningAgent
    r,p=inspect();a=ReasoningAgent.__new__(ReasoningAgent)
    a._governed_request=True;a.provider='offline';a.model='offline';a.temperature=0;a.max_tokens=1800
    a._persist_telemetry=lambda telemetry:(None,None)
    seen=[]
    def create(**kwargs):
        seen.append(kwargs)
        return NS(output_text='{}',usage=None,id='offline-only',model='offline',status='completed')
    a.client=NS(responses=NS(create=create))
    a._call_model(p,interaction_id='offline',reasoning_id='offline',stage='REASONING_FINAL')
    assert seen[0]['text']['format']['name']=='target_scoped_diagnosis'
    assert seen[0]['text']['format']['strict'] is True

def test_statement_order_and_json_format_do_not_define_semantic_scope():
    from runtime_observation.evidence_ledger import render_selection
    from integration.self_inspection_activation import assess
    r,p=inspect();l=r.context.self_inspection['evidence_ledger'];v=proposal(l)
    v['statements'].reverse();v['diagnosis']['evidence_ids'].reverse()
    text,_=render_selection(json.dumps(v,indent=4,sort_keys=True),p)
    assert assess(QUERY,p,text)['allowed']

@pytest.mark.parametrize('question',[
    'What capability prevents MODE from determining whether an evidence record can safely substitute for another?',
    'What prevents safe representative-evidence decisions?',
])
def test_declared_relation_grammar_is_not_exact_question_hardcoding(question):
    r,p=inspect(question)
    assert r.context.self_inspection['tool_request']['tool']=='inspect_target_sources'

def test_unsupported_negation_does_not_become_a_positive_target():
    r,p=inspect(QUESTION.replace('can safely represent','can not safely represent'))
    assert r.context.self_inspection['tool_request'] is None

def test_other_unknown_operative_target_cannot_inherit_enclosing_domain():
    q='Inspect your current Learning subsystem against this objective. Which mechanism prevents imaginary flux transmutation?'
    r,p=inspect(q);assert r.context.self_inspection['tool_request'] is None

def test_unhashable_model_citation_is_refused_as_a_contract_error():
    r,p=inspect();l=r.context.self_inspection['evidence_ledger'];v=proposal(l)
    v['diagnosis']['evidence_ids']=[[]]
    from runtime_observation.evidence_ledger import render_selection
    with pytest.raises(PermissionError):render_selection(json.dumps(v),p)

def test_unrelated_external_capability_question_does_not_inspect_MODE():
    from integration.self_inspection_activation import classify,objective_evidence_requirements
    q='Which capability helps a migratory bird navigate?'
    assert classify(q) is None and objective_evidence_requirements(q) is None

def test_unknown_target_runtime_refusal_preserves_question_not_domain():
    from integration.self_inspection_activation import bounded_result
    q='Inspect your current Learning subsystem against this objective. What capability prevents imaginary flux transmutation?'
    text=bounded_result(q)
    assert 'target UNKNOWN' in text and 'What capability prevents imaginary flux transmutation?' in text
    assert 'context only' in text
