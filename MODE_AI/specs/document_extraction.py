"""Extract source text without executing document instructions or promoting authority.

Preserved bytes are required. PDF/DOCX extraction is not rendered-page observation,
OCR, or a guarantee of visual/reading-order fidelity. Unsupported content is explicit.
"""
import base64
import hashlib
import io
import json
import zipfile
import xml.etree.ElementTree as ET

MAX_BYTES=8*1024*1024
MAX_TEXT=2*1024*1024


class _DocumentTree(ET.TreeBuilder):
    def doctype(self,name,pubid,system):
        raise ValueError('XML entity declarations are not supported')


def decode_source(content):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate binary source field')
            result[key]=value
        return result
    if type(content) is not str or len(content)>MAX_BYTES*2:raise ValueError('Bounded encoded source required')
    payload=json.loads(content,object_pairs_hook=unique)
    if type(payload) is not dict or set(payload)!={'schema_version','format','encoding','data','sha256'} or payload['schema_version']!='DocumentBinary/1' or payload['encoding']!='BASE64':
        raise ValueError('Explicit binary document source required')
    raw=base64.b64decode(payload['data'],validate=True)
    if len(raw)>MAX_BYTES or hashlib.sha256(raw).hexdigest()!=payload['sha256']:raise ValueError('Binary source size/hash mismatch')
    return payload,raw


def extract(content):
    payload,raw=decode_source(content)
    kind=payload['format'];segments=[];unresolved=[];structure=None
    if kind=='UTF8_TEXT':
        segments=[{'locator':'text:1','text':raw.decode('utf-8')}];mechanism='python:utf-8-strict'
    elif kind=='DOCX':
        structure={'tables':[],'sections':[],'figures':None,'citations':None}
        mechanism='python:zipfile+xml.etree.ElementTree'
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            members=package.infolist();names=[item.filename for item in members]
            if len(members)>1024 or len(set(names))!=len(names) or sum(item.file_size for item in members)>16*1024*1024:
                raise ValueError('DOCX package exceeds extraction bounds or contains duplicate parts')
            if 'word/document.xml' not in names:raise ValueError('DOCX document part missing')
            ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            ancillary=sorted(n for n in names if n.endswith('.xml') and n.startswith(
                ('word/header','word/footer','word/footnotes','word/endnotes','word/comments')))
            for part in ['word/document.xml']+ancillary:
                xml=package.read(part)
                if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:raise ValueError('XML entity declarations are not supported')
                root=ET.fromstring(xml,parser=ET.XMLParser(target=_DocumentTree()))
                paragraph_locations={id(p):('' if part=='word/document.xml' else part+':')+'paragraph:'+str(i)
                    for i,p in enumerate(root.iter(ns+'p'),1)}
                for index,table in enumerate(root.iter(ns+'tbl'),1):
                    rows=[]
                    for row in table.findall(ns+'tr'):
                        rows.append([{'paragraph_references':[paragraph_locations[id(p)] for p in cell.iter(ns+'p')],
                            'grid_span':cell.find(ns+'tcPr/'+ns+'gridSpan').get(ns+'val') if cell.find(ns+'tcPr/'+ns+'gridSpan') is not None else None,
                            'vertical_merge':dict(cell.find(ns+'tcPr/'+ns+'vMerge').attrib) if cell.find(ns+'tcPr/'+ns+'vMerge') is not None else None}
                            for cell in row.findall(ns+'tc')])
                    structure['tables'].append({'source_locator':part+':table:'+str(index),'rows':rows,
                        'layout_validated':False})
                for index,section in enumerate(root.iter(ns+'sectPr'),1):
                    structure['sections'].append({'source_locator':part+':section-properties:'+str(index),
                        'properties':[{'name':node.tag,'attributes':dict(node.attrib)} for node in section],
                        'semantic_section':False})
                def paragraph_nodes(node,initial=True):
                    if not initial and node.tag==ns+'p':
                        if 'NESTED_PARAGRAPH_PLACEMENT_NOT_RESOLVED' not in unresolved:
                            unresolved.append('NESTED_PARAGRAPH_PLACEMENT_NOT_RESOLVED')
                        return
                    yield node
                    for child in node:yield from paragraph_nodes(child,False)
                for index,paragraph in enumerate(root.iter(ns+'p'),1):
                    text=''.join(node.text or '' if node.tag==ns+'t' else '\t' if node.tag==ns+'tab' else '\n'
                                 for node in paragraph_nodes(paragraph) if node.tag in {ns+'t',ns+'tab',ns+'br',ns+'cr'})
                    locator=('' if part=='word/document.xml' else part+':')+'paragraph:'+str(index)
                    # Empty paragraphs still have identity (including empty
                    # table cells); structural references must remain resolvable.
                    segments.append({'locator':locator,'text':text})
                if next(root.iter(ns+'tbl'),None) is not None and 'TABLE_LAYOUT_NOT_PRESERVED' not in unresolved:
                    unresolved.append('TABLE_LAYOUT_NOT_PRESERVED')
                if (next(root.iter(ns+'del'),None) is not None or next(root.iter(ns+'ins'),None) is not None) and 'TRACKED_CHANGES_REQUIRE_REVIEW' not in unresolved:
                    unresolved.append('TRACKED_CHANGES_REQUIRE_REVIEW')
            unresolved.append('VISUAL_LAYOUT_NOT_OBSERVED')
            if any(n.startswith('word/media/') for n in names):unresolved.append('EMBEDDED_MEDIA_NOT_INTERPRETED')
            if ancillary:unresolved.append('ANCILLARY_PLACEMENT_NOT_RESOLVED')
    elif kind=='PDF':
        # Optional parser; absence is an error, never invented extraction success.
        import pypdf
        mechanism='pypdf:'+pypdf.__version__
        reader=pypdf.PdfReader(io.BytesIO(raw),strict=True)
        if reader.is_encrypted:raise PermissionError('Encrypted PDF requires separate authorized handling')
        if len(reader.pages)>64:raise ValueError('PDF page extraction bound exceeded')
        unresolved.extend(['VISUAL_LAYOUT_NOT_OBSERVED','PDF_READING_ORDER_NOT_VALIDATED'])
        total=0
        for index,page in enumerate(reader.pages,1):
            text=page.extract_text() or '';total+=len(text)
            if total>MAX_TEXT:raise ValueError('Extracted text exceeds bound')
            segments.append({'locator':'page:'+str(index),'text':text})
            if not text.strip():unresolved.append('PAGE_'+str(index)+'_HAS_NO_EXTRACTABLE_TEXT')
    else:raise ValueError('Unsupported document extraction format')
    if sum(len(s['text']) for s in segments)>MAX_TEXT:raise ValueError('Extracted text exceeds bound')
    if not any(s['text'].strip() for s in segments):unresolved.append('NO_EXTRACTABLE_TEXT')
    return {'contract':'DocumentTextExtraction/1','format':kind,'binary_sha256':payload['sha256'],
        'mechanism_reference':mechanism,'segments':segments,'structure':structure,'unresolved':unresolved,
        'state':'REVIEW_REQUIRED' if unresolved else 'TEXT_EXTRACTED','kind':'DRAFT',
        'rendered_output_observed':False,'claims_validated':False,'execution_authority':False}
