import hashlib
import json
import pytest
from specs.document_service import DocumentService
from system_layer.contracts import digest

def test_export_keeps_source_and_cannot_execute_embedded_html(tmp_path):
    docs=DocumentService(tmp_path/'docs.db')
    req=dict(object_id='source',content='<script>alert(1)</script>\nOriginal wording.',kind='DRAFT',visual_authority='NOT_APPLICABLE',
        knowledge_class='INTERNAL',source_reference='operator:1',authority='operator',project_id='p',thread_id='t',
        expected_previous=None,validation_references=[])
    record=docs.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
    for format in ('TEXT','JSON','HTML'):
        value=docs.export('op','source',1,record['record_hash'],format)
        assert value['sha256']==hashlib.sha256(value['content'].encode()).hexdigest()
        assert value['rendered_output_observed'] is False
        if format=='TEXT':assert value['content']==req['content']
        if format=='JSON':assert json.loads(value['content'])==record
        if format=='HTML':assert '<script>' not in value['content'] and '&lt;script&gt;' in value['content']
    with pytest.raises(ValueError):docs.export('op','source',1,'changed','TEXT')
