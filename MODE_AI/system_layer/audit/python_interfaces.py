"""Static Python call signatures, without imports, evaluation, or default values."""
import ast


def _annotation(node):
    if node is None:return {'state':'NOT_DECLARED','text':None}
    allowed=(ast.Name,ast.Attribute,ast.Subscript,ast.Tuple,ast.List,ast.Load,ast.BinOp,ast.BitOr)
    if all(isinstance(n,allowed) or isinstance(n,ast.Constant) and n.value is None for n in ast.walk(node)):
        return {'state':'DECLARED_SYNTAX_ONLY','text':ast.unparse(node)}
    return {'state':'UNRESOLVED_EXPRESSION','text':None}


def interfaces(tree):
    result=[]
    def visit(node,parents=()):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            parameters=[];args=node.args;positional=args.posonlyargs+args.args
            defaults_start=len(positional)-len(args.defaults)
            for index,arg in enumerate(positional):
                parameters.append({'name':arg.arg,'kind':'POSITIONAL_ONLY' if index<len(args.posonlyargs) else 'POSITIONAL_OR_KEYWORD',
                    'has_default':index>=defaults_start,'annotation':_annotation(arg.annotation)})
            if args.vararg:parameters.append({'name':args.vararg.arg,'kind':'VAR_POSITIONAL','has_default':False,'annotation':_annotation(args.vararg.annotation)})
            for arg,default in zip(args.kwonlyargs,args.kw_defaults):
                parameters.append({'name':arg.arg,'kind':'KEYWORD_ONLY','has_default':default is not None,'annotation':_annotation(arg.annotation)})
            if args.kwarg:parameters.append({'name':args.kwarg.arg,'kind':'VAR_KEYWORD','has_default':False,'annotation':_annotation(args.kwarg.annotation)})
            result.append({'qualified_name':'.'.join(parents+(node.name,)),'line':node.lineno,
                'async':isinstance(node,ast.AsyncFunctionDef),'parameters':parameters,
                'return_annotation':_annotation(node.returns),'default_values':'NOT_CAPTURED',
                'execution_authority':False,'runtime_callable':'NOT_ESTABLISHED'})
        nested=parents+(node.name,) if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) else parents
        for child in ast.iter_child_nodes(node):visit(child,nested)
    visit(tree)
    return result
