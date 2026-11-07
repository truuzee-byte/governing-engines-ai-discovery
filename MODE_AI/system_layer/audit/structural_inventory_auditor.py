"""System Layer v1.2 §8A: bounded, non-executing structure inventory.

Only individually authorized relative files are read. No imports, subprocesses,
recursive discovery, or source contents are returned. Missing or uninspectable
structure remains explicit. A snapshot is not an operational capability verdict.
"""
import ast
import hashlib
from pathlib import Path, PureWindowsPath
import stat
from ..contracts import digest, now

MAX_FILES = 256
MAX_FILE_BYTES = 2 * 1024 * 1024


def validate_selection(root, files):
    root = Path(root)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError('Existing absolute inventory root required')
    if type(files) is not list or not 0 < len(files) <= MAX_FILES:
        raise ValueError('Explicit bounded file selection required')
    if any(type(name) is not str or not name.strip() for name in files):
        raise ValueError('Inventory file names must be nonempty strings')
    canonical = []
    for name in files:
        path = PureWindowsPath(name)
        if path.is_absolute() or path.drive or '..' in path.parts or ':' in name:
            raise ValueError('Inventory selection escapes its authorized root')
        normalized = name.replace('\\', '/')
        if normalized.startswith('/') or normalized != '/'.join(path.parts):
            raise ValueError('Canonical relative file paths required')
        canonical.append(normalized)
    if len({name.casefold() for name in canonical}) != len(canonical):
        raise ValueError('Duplicate inventory paths')
    return root, canonical


def _read(root, name):
    path = root / name
    # Reject links/reparse points in every component, including the root ancestry.
    for part in [path, *path.parents]:
        metadata = part.lstat()
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked inventory source is not admitted')
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Inventory source is not an ordinary contained file')
    with path.open('rb') as stream:
        content = stream.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValueError('Inventory file exceeds bounded read limit')
    return content


def inspect(root, files, *, system_id, system_version, scope, version=1, supersedes=None):
    root, files = validate_selection(root, files)
    if any(type(v) is not str or not v.strip() for v in (system_id, system_version)):
        raise ValueError('Exact system identity and version required')
    if type(scope) is not dict or not scope.get('operator_id') or not scope.get('purpose'):
        raise ValueError('Operator and bounded inspection purpose required')
    if type(version) is not int or version < 1 or (version > 1 and not supersedes):
        raise ValueError('Inventory version lineage required')
    entries = []
    for name in sorted(files):
        entry = {'path': name, 'state': 'UNAVAILABLE', 'sha256': None, 'structure': None}
        try:
            content = _read(root, name)
            entry.update(sha256=hashlib.sha256(content).hexdigest(), size=len(content), state='INSPECTED')
            if name.endswith('.py'):
                tree = ast.parse(content, filename=name)
                from .python_interfaces import interfaces
                entry['structure'] = {
                    'interfaces':interfaces(tree),
                    'classes': sorted(n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)),
                    'functions': sorted(n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))),
                    'imports': sorted({a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
                                      | {n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}),
                }
            elif name.endswith(('.uproject','.uplugin')) or name.endswith('/Build.version') or name=='Build.version':
                from .unreal_structure import parse
                kind='PROJECT' if name.endswith('.uproject') else 'PLUGIN' if name.endswith('.uplugin') else 'version'
                entry['structure']=parse(content,kind)
            elif name.endswith(('.h','.hpp','.cpp','.cs')):
                from .unreal_structure import native_candidates
                entry['structure']=native_candidates(content)
            elif name.endswith('.json'):
                from io import StringIO
                from data_governance.custody_json import load
                value = load(StringIO(content.decode('utf-8-sig')))
                entry['structure'] = {'root_type': type(value).__name__,
                    'keys': sorted(value) if type(value) is dict else []}
            else:
                entry['structure'] = {'interpretation': 'NOT_PARSED'}
        except FileNotFoundError:
            entry['state'] = 'MISSING'
        except (OSError, ValueError, SyntaxError, UnicodeError) as exc:
            entry['state'] = 'UNINSPECTABLE'
            entry['error_type'] = type(exc).__name__
        entries.append(entry)
    record = {'schema_version': 'StructuralInventory/1.2', 'system_id': system_id,
        'system_version': system_version, 'scope': dict(scope), 'root': str(root),
        'selection': sorted(files), 'version': version, 'supersedes': supersedes,
        'observed_at': now(), 'entries': entries,
        'completeness': 'COMPLETE_FOR_SELECTION' if all(e['state'] == 'INSPECTED' for e in entries) else 'PARTIAL',
        'uninspected_scope': 'Everything outside the explicit selection',
        'operational_state': 'UNPROVEN', 'execution_authority': 'NONE'}
    record['inventory_hash'] = digest(record)
    return record


def freshness(record):
    """Re-read the exact selection; no source description can override drift."""
    original = dict(record)
    checksum = original.pop('inventory_hash', None)
    if checksum != digest(original):
        raise ValueError('Inventory integrity mismatch')
    if record.get('schema_version')!='StructuralInventory/1.2':
        raise ValueError('Unsupported structural inventory contract')
    _,selection=validate_selection(record['root'],record['selection'])
    entries=record.get('entries')
    if (type(entries) is not list or any(type(entry) is not dict for entry in entries)
            or [entry.get('path') for entry in entries]!=sorted(selection)):
        raise ValueError('Inventory must retain exactly one entry for every selected source')
    current = inspect(record['root'], record['selection'], system_id=record['system_id'],
        system_version=record['system_version'], scope=record['scope'])
    changed = [entry['path'] for entry, old in zip(current['entries'], entries) if entry != old]
    return {'state': 'REVALIDATION_REQUIRED' if changed or current['completeness'] == 'PARTIAL' else 'CURRENT_FOR_SELECTION',
            'changed_paths': changed, 'inventory_hash': checksum,
            'operational_state': 'UNPROVEN', 'execution_authority': 'NONE'}
