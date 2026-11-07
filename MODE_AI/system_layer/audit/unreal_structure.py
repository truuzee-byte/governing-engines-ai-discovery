"""Read declared Unreal descriptor structure, never infer a working installation."""
import json
import re


def native_candidates(content):
    """Lexical index only: no preprocessing, overload resolution or operability claim."""
    text=content.decode('utf-8-sig')
    # Remove comments while preserving quoted literals and line numbers.
    pattern=r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    text=re.sub(pattern,lambda m:'\n'*m.group().count('\n') if m.group().startswith(('//','/*')) else m.group(),text)
    includes=sorted(set(re.findall(r'^\s*#\s*include\s*[<"]([^>"\n]+)[>"]',text,re.M)))
    declarations=[]
    for line_number,line in enumerate(text.splitlines(),1):
        match=re.match(r'\s*(?:public\s+|private\s+|internal\s+|sealed\s+|abstract\s+)*(?:class|struct)\s+(?:[A-Z][A-Z0-9_]*_API\s+)?([A-Za-z_]\w*)',line)
        if match:declarations.append({'name':match[1],'line':line_number,'kind':'TYPE_CANDIDATE'})
        # Only explicit static declarations; bodies/macros can require later
        # semantic analysis. Keep these as candidates, never callable promises.
        match=re.match(r'\s*(?:public\s+|private\s+|internal\s+)?static\s+[^=;{}]+?\b([A-Za-z_]\w*)\s*\(',line)
        if match:declarations.append({'name':match[1],'line':line_number,'kind':'STATIC_INTERFACE_CANDIDATE'})
    return {'interpretation':'LEXICAL_CANDIDATES_ONLY','includes':includes,'declarations':declarations,
            'unresolved':['PREPROCESSING','SIGNATURE_RESOLUTION','RUNTIME_ACCESS','OPERATIONAL_VALIDATION']}


def parse(content,kind):
    if kind not in {'PROJECT','PLUGIN','version'}:raise ValueError('Unknown Unreal descriptor kind')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate descriptor key')
            result[key]=value
        return result
    text=content.decode('utf-8-sig') if isinstance(content,bytes) else content
    transformations=[]
    if kind in {'PROJECT','PLUGIN'}:
        # UE 5.7 JsonReader.h ReadNextArrayValue accepts SquareClose after a
        # comma. ReadNextObjectValue still requires a String in that position.
        # Preserve quoted strings and reject missing values/doubled commas.
        def array_comma(match):
            if match.group().startswith('"'):return match.group()
            before=text[:match.start()].rstrip()
            if not before or before[-1] in '[,:':return match.group()
            transformations.append({'character_offset':match.start(),'kind':'ARRAY_TRAILING_COMMA'})
            return match.group()[1:]
        text=re.sub(r'"(?:\\.|[^"\\])*"|,\s*(?=\])',array_comma,text)
    def invalid_constant(value):raise ValueError('Non-finite descriptor value')
    value=json.loads(text,object_pairs_hook=unique,parse_constant=invalid_constant)
    if type(value) is not dict:raise ValueError('Object descriptor required')
    if kind=='version':
        fields=('MajorVersion','MinorVersion','PatchVersion','Changelist','CompatibleChangelist','BranchName')
        for key in fields[:-1]:
            if key in value and (type(value[key]) is not int or value[key]<0):raise ValueError('Invalid engine version')
        return {'descriptor_kind':'ENGINE_VERSION','declared':{k:value[k] for k in fields if k in value},
                'unresolved':[k for k in fields if k not in value],'operability':'UNPROVEN'}
    result={'descriptor_kind':kind,'modules':None,'plugins':None,'engine_association':value.get('EngineAssociation'),
            'parse_transformations':transformations,'parser_scope':'JSON_WITH_UE_ARRAY_TRAILING_COMMAS',
            'unresolved':[],'operability':'UNPROVEN','uninterpreted_fields':sorted(set(value)-{'Modules','Plugins','EngineAssociation'})}
    for source,target in (('Modules','modules'),('Plugins','plugins')):
        if source not in value:result['unresolved'].append(source);continue
        if type(value[source]) is not list:raise ValueError('Descriptor list required')
        seen=set();items=[]
        for entry in value[source]:
            if type(entry) is not dict or type(entry.get('Name')) is not str or not entry['Name'].strip():
                raise ValueError('Named descriptor relationship required')
            if entry['Name'] in seen:raise ValueError('Duplicate descriptor relationship')
            seen.add(entry['Name'])
            # Retain flags, platform constraints and dependencies exactly rather
            # than turn a declared module into an enabled/loaded capability.
            items.append(entry)
        result[target]=items
    return result
