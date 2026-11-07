"""Authorized directory metadata discovery preceding exact-file inventory.

System v1.2 §8A: discover machine-readable source instead of asking the Operator
to transcribe it. This does not inspect content, import code, or establish access
for execution. Bounds and unreadable/linked entries remain explicit.
"""
import os
import stat
from pathlib import Path
from ..contracts import digest


def discover(root,extensions,limit):
    root=Path(root)
    if not root.is_absolute() or not root.is_dir():raise ValueError('Existing absolute discovery root required')
    if type(limit) is not int or not 1<=limit<=256:raise ValueError('Bounded discovery selection required')
    if type(extensions) is not list or not extensions or len(extensions)>32 or any(
        type(e) is not str or not e.startswith('.') or len(e)>32 or not e[1:].isalnum() for e in extensions):
        raise ValueError('Explicit filename extensions required')
    for part in [root,*root.parents]:
        metadata=part.lstat()
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata,'st_file_attributes',0)&0x400:
            raise ValueError('Linked discovery root is not admitted')
    pending=[(root,0)];files=[];issues=[];examined=0;directories=0
    suffixes={e.casefold() for e in extensions};limited=False
    while pending:
        directory,depth=pending.pop();directories+=1
        if directories>256:
            limited=True;break
        try:
            children=[]
            with os.scandir(directory) as entries:
                for entry in entries:
                    examined+=1
                    if examined>4096:limited=True;break
                    relative=Path(entry.path).relative_to(root).as_posix()
                    try:
                        info=entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                            issues.append({'path':relative,'state':'LINK_NOT_FOLLOWED'});continue
                        if stat.S_ISDIR(info.st_mode):
                            if depth>=16:issues.append({'path':relative,'state':'DEPTH_LIMIT'});continue
                            children.append((Path(entry.path),depth+1))
                        elif stat.S_ISREG(info.st_mode) and Path(entry.name).suffix.casefold() in suffixes:
                            files.append({'path':relative,'size':info.st_size,'mtime_ns':info.st_mtime_ns,
                                'state':'DISCOVERED_NOT_INSPECTED','sha256':None})
                    except OSError as exc:issues.append({'path':relative,'state':'UNAVAILABLE','error_type':type(exc).__name__})
            pending.extend(sorted(children,reverse=True))
            if limited:break
        except OSError as exc:issues.append({'path':directory.relative_to(root).as_posix(),'state':'UNAVAILABLE','error_type':type(exc).__name__})
    ordered=sorted(files,key=lambda value:value['path']);selection=ordered[:limit]
    value={'contract':'StructuralSourceDiscovery/1','root':str(root),'extensions':extensions,'limit':limit,
        'files':selection,'discovered_matches_in_window':len(ordered),'examined_entries':min(examined,4096),
        'issues':issues,'state':'PARTIAL' if limited or issues or len(ordered)>limit else 'COMPLETE_FOR_SELECTED_EXTENSIONS',
        'results_limited':len(ordered)>limit,'enumeration_limited':limited,'source_contents_read':False,
        'execution_authority':False,'operability':'UNPROVEN'}
    value['discovery_hash']=digest(value)
    return value
