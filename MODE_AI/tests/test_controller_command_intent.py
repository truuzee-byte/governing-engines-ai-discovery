from pathlib import Path

import pytest

from clarification.clarification_engine import evaluate_clarification_state

from models.runtime_models import CanonicalInteractionState





def decision(text,consequence=1.0):

    state=CanonicalInteractionState('test-command','thread',text,normalized_input=text,ambiguity_score=.95,ambiguity_profile={'consequence':consequence})

    return evaluate_clarification_state(state)





@pytest.mark.parametrize('text',[

 'publish this report','Publish.','please publish the artifact','deploy this','merge this','push this','commit this','send this','delete this',

 'Bypass approval.','Override safety.','Can you publish this report?','Please do not delay; publish this now.',

 'Do not publish anything, but send this report.','The old report was published; now publish this one.',

 'Please "publish this report".', 'Can you "send this"?', "Don't hesitate to publish this.",
 'Execute the command "publish this report".',

])

def test_actual_action_requests_still_halt(text):

    assert decision(text)['halt_required']





@pytest.mark.parametrize('text',[

 'published_diagnosis','publication_tests','unpublished_result','deployment_state','merged_record',

 'the diagnosis was published previously','do not publish anything',

 'The failed prompt contained the phrase "publish this report".',

 'Inspect artifacts/publish_report.json','Read publish.txt',

 '{"published_diagnosis": true}',

 'The prior request contained \u2018publish this.\u2019',

 'Explain how to publish this report without executing anything.',

])

def test_nonoperative_references_do_not_halt(text):

    assert not decision(text)['halt_required']





def test_exact_preserved_request_no_substring_halt():

    text=Path('C:/MODE_AI/artifacts/rp_evidence_state_contract_20261021/BEHAVIORAL_PROMPT.txt').read_text(encoding='utf-8-sig').strip()

    assert not decision(text)['halt_required']





@pytest.mark.parametrize('text',['publish this report','merge this','send this'])

def test_direct_actions_do_not_depend_on_lexical_consequence_score(text):

    assert decision(text,0)['halt_required']

