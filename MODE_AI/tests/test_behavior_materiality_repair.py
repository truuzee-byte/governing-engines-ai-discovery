"""Descriptions of requirements are not assertions that requirements were met."""
from types import SimpleNamespace as NS
import pytest
from data_governance.response_gate import evaluate


def runtime():return NS(context=NS(identity=NS(operator_id='op'),active_thread=NS(thread_id='t')))


@pytest.mark.parametrize('text',[
    'Would you like this information saved to Persistent Memory?',
    'Evidence of the intended outcome refers to a verified state change.',
    'Verifying authenticity is important for accurate evaluation.',
    'The specification describes approval requirements for deployment.',
    'Unknown causes remain unresolved. No execution is being claimed.',
    'The document is not authoritative.',
    '1. Interpretation\nThe question concerns validation.\n2. Reasoning\nThe specification describes approval requirements for deployment.',
])
def test_descriptive_keywords_do_not_manufacture_materiality(text):
    result=evaluate(runtime(),'Explain the distinction.',text)
    assert result['allowed'] and not result['material']
    assert not result['execution_authority_granted']


@pytest.mark.parametrize('assertion',[
    'The service is operational.', 'The artifact passed validation.',
    'I saved the value permanently.', 'You may deploy it.',
    'I approve the release.', 'The audit has established compliance.',
    'AUTHORIZED', 'Access granted.', 'The release has been approved.',
    'The admitted draft note remains authoritative for broader permissions.',
    'The imported source is the authoritative source for deployment.',
    'The document grants authority to execute.',
])
def test_positive_claim_after_description_is_still_gated(assertion):
    result=evaluate(runtime(),'Explain.', 'The specification describes approval requirements. '+assertion)
    assert not result['allowed'] and result['material']


def test_explicit_material_claim_still_requires_signed_scope():
    r=runtime();r.context.material_response_claim={'claim_id':'claim'}
    assert not evaluate(r,'Explain.','A descriptive explanation.')['allowed']
