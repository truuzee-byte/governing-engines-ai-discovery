from system_layer.audit.structural_inventory_auditor import inspect


def test_python_signatures_preserve_parameter_kinds_without_default_execution_or_content(tmp_path):
    (tmp_path/'tool.py').write_text('''raise RuntimeError("do not import")
class Tool:
    async def run(self, source: str, /, count: int = dangerous("private literal"), *items, flag: bool, optional=None, **options) -> list[str]:
        pass
''')
    result=inspect(str(tmp_path),['tool.py'],system_id='tool',system_version='1',scope={'operator_id':'op','purpose':'Understand signatures'})
    signature=result['entries'][0]['structure']['interfaces'][0]
    assert signature['qualified_name']=='Tool.run' and signature['async']
    assert [p['kind'] for p in signature['parameters']]==['POSITIONAL_ONLY','POSITIONAL_ONLY','POSITIONAL_OR_KEYWORD','VAR_POSITIONAL','KEYWORD_ONLY','KEYWORD_ONLY','VAR_KEYWORD']
    assert signature['parameters'][2]['has_default'] and not signature['parameters'][4]['has_default']
    assert signature['return_annotation']['text']=='list[str]'
    assert 'private literal' not in str(result)
    assert signature['runtime_callable']=='NOT_ESTABLISHED'
