import base64
import hashlib
import io
import json
import zipfile
import pytest
from specs.document_extraction import extract
from specs.document_service import DocumentService
from system_layer.contracts import digest


def encoded(raw,kind):
    return json.dumps(dict(schema_version='DocumentBinary/1',format=kind,encoding='BASE64',data=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest()))


def test_docx_extracts_exact_text_and_retains_unresolved_structure():
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as package:
        package.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Exact author words.</w:t><w:tab/><w:t>Second phrase.</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cell text.</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        package.writestr('word/media/image.png',b'not decoded')
    value=extract(encoded(stream.getvalue(),'DOCX'))
    assert [s['text'] for s in value['segments']]==['Exact author words.\tSecond phrase.','Cell text.']
    assert 'TABLE_LAYOUT_NOT_PRESERVED' in value['unresolved'] and 'EMBEDDED_MEDIA_NOT_INTERPRETED' in value['unresolved']
    assert value['state']=='REVIEW_REQUIRED' and not value['rendered_output_observed']
    table=value['structure']['tables'][0]
    assert table['rows'][0][0]['paragraph_references']==['paragraph:2']
    assert not table['layout_validated']
    assert value['structure']['figures'] is None


def test_docx_ancillary_text_retains_part_locators_without_claiming_page_order():
    stream=io.BytesIO();parts=['word/document.xml','word/header1.xml','word/footer1.xml','word/footnotes.xml','word/endnotes.xml','word/comments.xml']
    with zipfile.ZipFile(stream,'w') as package:
        for part in parts:
            package.writestr(part,'<w:root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>'+part+'</w:t></w:r></w:p></w:root>')
    value=extract(encoded(stream.getvalue(),'DOCX'))
    assert {s['text'] for s in value['segments']}==set(parts)
    assert value['segments'][0]=={'locator':'paragraph:1','text':'word/document.xml'}
    for segment in value['segments'][1:]:assert segment['locator']==segment['text']+':paragraph:1'
    assert 'ANCILLARY_PLACEMENT_NOT_RESOLVED' in value['unresolved']
    assert value['state']=='REVIEW_REQUIRED' and not value['rendered_output_observed']


def test_empty_table_paragraph_keeps_resolvable_structure_reference():
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as package:
        package.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:tbl><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl><w:sectPr><w:pgSz w:w="100"/></w:sectPr></w:body></w:document>')
    result=extract(encoded(stream.getvalue(),'DOCX'))
    ref=result['structure']['tables'][0]['rows'][0][0]['paragraph_references'][0]
    assert result['segments']==[{'locator':ref,'text':''}]
    assert result['structure']['sections'][0]['semantic_section'] is False
    assert 'NO_EXTRACTABLE_TEXT' in result['unresolved']


def test_docx_utf16_entity_declaration_is_rejected_in_ancillary_part():
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as package:
        package.writestr('word/document.xml','<root/>')
        package.writestr('word/header1.xml',('<?xml version="1.0" encoding="UTF-16"?>'
            '<!DOCTYPE root [<!ENTITY injected "substitution">]><root>&injected;</root>').encode('utf-16'))
    with pytest.raises(ValueError,match='entity declarations'):extract(encoded(stream.getvalue(),'DOCX'))


def test_docx_nested_text_box_paragraph_is_not_duplicated():
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as package:
        package.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:p><w:r><w:t>Outer paragraph</w:t><w:drawing><w:txbxContent><w:p><w:r><w:t>Text box</w:t></w:r>'
            '</w:p></w:txbxContent></w:drawing></w:r></w:p></w:document>')
    value=extract(encoded(stream.getvalue(),'DOCX'))
    assert [s['text'] for s in value['segments']]==['Outer paragraph','Text box']
    assert 'NESTED_PARAGRAPH_PLACEMENT_NOT_RESOLVED' in value['unresolved']


def test_pdf_without_text_is_not_fake_extraction_or_visual_proof():
    from pypdf import PdfWriter
    writer=PdfWriter();writer.add_blank_page(width=100,height=100);stream=io.BytesIO();writer.write(stream)
    value=extract(encoded(stream.getvalue(),'PDF'))
    assert value['segments']==[{'locator':'page:1','text':''}]
    assert 'NO_EXTRACTABLE_TEXT' in value['unresolved'] and value['state']=='REVIEW_REQUIRED'


def test_preserved_binary_scope_and_hash_survive_extraction(tmp_path):
    docs=DocumentService(tmp_path/'docs.db');content=encoded('Exact café\nNext line'.encode(),'UTF8_TEXT')
    req=dict(object_id='source',content=content,kind='AUTHORITATIVE',visual_authority='NOT_APPLICABLE',knowledge_class='EXTERNAL',
        source_reference='operator:file',authority='operator',project_id='p',thread_id='t',expected_previous=None,validation_references=[])
    record=docs.intake('op',req,dict(operator_id='op',action='DOCUMENT_INTAKE',decision='APPROVE',hash=digest(req)))
    value=docs.extract_text('op','source',1,record['record_hash'],'p')
    assert value['segments'][0]['text']=='Exact café\nNext line' and value['source_knowledge_class']=='EXTERNAL'
    assert value['source_record_hash']==record['record_hash'] and value['kind']=='DRAFT' and not value['persisted']
    assert docs.retrieve('op','source',1,record['record_hash'])==record
    with pytest.raises(PermissionError):docs.extract_text('op','source',1,record['record_hash'],'other')
    payload=json.loads(content);payload['sha256']='0'*64
    with pytest.raises(ValueError,match='hash mismatch'):extract(json.dumps(payload))
