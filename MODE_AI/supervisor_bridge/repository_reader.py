from __future__ import annotations

import subprocess
import stat
import os
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RepositoryAccessError(RuntimeError):
    pass



class WindowsDirectoryBinding:
    """Local NTFS, read-only, no-reparse handle chain; no pathname enumeration.

    NtCreateFile opens one component relative to an already-held parent. All
    components stay open without WRITE/DELETE sharing until validation and
    enumeration finish. Directory records supply child metadata without opens.
    """
    _api = None

    @staticmethod
    def lexical(value):
        import re
        path=Path(value)
        text=str(path)
        if os.name!='nt' or not path.is_absolute() or not re.fullmatch('[A-Za-z]:',path.drive):
            raise RepositoryAccessError('Native containment requires an absolute local Windows drive path')
        if any(part in ('.','..') or part.endswith((' ','.')) or ':' in part or '\x00' in part or len(part.encode('utf-16-le'))>510
               for part in path.parts[1:]):
            raise RepositoryAccessError('Ambiguous or unsafe native directory component')
        return path

    @classmethod
    def api(cls):
        if cls._api is not None:return cls._api
        if os.name!='nt':raise RepositoryAccessError('Windows handle containment unavailable; no path fallback')
        import ctypes as c
        from ctypes import wintypes as w
        if c.sizeof(c.c_void_p)!=8:raise RepositoryAccessError('Only tested 64-bit Windows ABI is admitted')
        class Unicode(c.Structure):_fields_=[('Length',w.USHORT),('MaximumLength',w.USHORT),('Buffer',c.c_void_p)]
        class Attributes(c.Structure):_fields_=[('Length',w.ULONG),('RootDirectory',w.HANDLE),('ObjectName',c.POINTER(Unicode)),('Attributes',w.ULONG),('SecurityDescriptor',c.c_void_p),('SecurityQualityOfService',c.c_void_p)]
        class IO(c.Structure):_fields_=[('Status',c.c_void_p),('Information',c.c_size_t)]
        class Basic(c.Structure):_fields_=[('CreationTime',c.c_longlong),('LastAccessTime',c.c_longlong),('LastWriteTime',c.c_longlong),('ChangeTime',c.c_longlong),('FileAttributes',w.DWORD)]
        class Identity(c.Structure):_fields_=[('VolumeSerialNumber',c.c_ulonglong),('FileId',c.c_ubyte*16)]
        class Entry(c.Structure):
            _fields_=[('NextEntryOffset',w.DWORD),('FileIndex',w.DWORD),('CreationTime',c.c_longlong),('LastAccessTime',c.c_longlong),('LastWriteTime',c.c_longlong),('ChangeTime',c.c_longlong),('EndOfFile',c.c_longlong),('AllocationSize',c.c_longlong),('FileAttributes',w.DWORD),('FileNameLength',w.DWORD),('EaSize',w.DWORD),('ShortNameLength',c.c_byte),('ShortName',w.WCHAR*12),('FileId',c.c_longlong),('FileName',w.WCHAR*1)]
        k=c.WinDLL('kernel32',use_last_error=True);nt=c.WinDLL('ntdll',use_last_error=True)
        k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE];k.CreateFileW.restype=w.HANDLE
        k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL
        k.GetFileInformationByHandleEx.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD];k.GetFileInformationByHandleEx.restype=w.BOOL
        k.ReadFile.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p];k.ReadFile.restype=w.BOOL
        k.GetFileType.argtypes=[w.HANDLE];k.GetFileType.restype=w.DWORD
        k.GetDriveTypeW.argtypes=[w.LPCWSTR];k.GetDriveTypeW.restype=w.UINT
        k.GetVolumeInformationByHandleW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,c.POINTER(w.DWORD),c.POINTER(w.DWORD),c.POINTER(w.DWORD),w.LPWSTR,w.DWORD];k.GetVolumeInformationByHandleW.restype=w.BOOL
        k.GetFinalPathNameByHandleW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,w.DWORD];k.GetFinalPathNameByHandleW.restype=w.DWORD
        nt.NtCreateFile.argtypes=[c.POINTER(w.HANDLE),w.ULONG,c.POINTER(Attributes),c.POINTER(IO),c.c_void_p,w.ULONG,w.ULONG,w.ULONG,w.ULONG,c.c_void_p,w.ULONG];nt.NtCreateFile.restype=c.c_long
        nt.RtlNtStatusToDosError.argtypes=[w.ULONG];nt.RtlNtStatusToDosError.restype=w.ULONG
        if Entry.FileName.offset!=104 or c.sizeof(Attributes)!=48:raise RepositoryAccessError('Unexpected native directory ABI')
        cls._api=(c,w,k,nt,Unicode,Attributes,IO,Basic,Identity,Entry)
        return cls._api

    def __init__(self,root,target=None,*,file=False):
        self.root=self.lexical(root);self.target=self.lexical(target or root)
        try:self.target.relative_to(self.root)
        except ValueError as exc:raise RepositoryAccessError('Native target outside authorized root') from exc
        self.is_file=file;self.file_handle=None
        if file and self.target==self.root:raise RepositoryAccessError('A file below the authorized root required')
        self.handles=[];self.root_handle=None;self.target_handle=None

    def _query(self,handle,kind,record_type):
        if handle not in self.handles:raise RepositoryAccessError('Directory handle is not retained')
        c,w,k,*_=self.api();value=record_type()
        if not k.GetFileInformationByHandleEx(handle,kind,c.byref(value),c.sizeof(value)):
            raise RepositoryAccessError('Native directory metadata unavailable: '+str(c.WinError(c.get_last_error())))
        return value

    def _retain(self,handle):
        self.handles.append(handle)
        Basic=self.api()[7];info=self._query(handle,0,Basic)
        if info.FileAttributes&0x400 or not info.FileAttributes&0x10:
            raise RepositoryAccessError('Reparse or non-directory component denied before traversal')
        return handle

    def _open_anchor(self):
        c,w,k,*_=self.api();anchor=self.root.anchor
        if k.GetDriveTypeW(anchor)!=3:raise RepositoryAccessError('Only local fixed NTFS volumes supported')
        handle=k.CreateFileW('\\\\?\\'+anchor,0x100081,1,None,3,0x02200000,None)
        if handle==c.c_void_p(-1).value:raise RepositoryAccessError('Native volume-root open denied: '+str(c.WinError(c.get_last_error())))
        self._retain(handle)
        fs=c.create_unicode_buffer(32)
        if not k.GetVolumeInformationByHandleW(handle,None,0,None,None,None,fs,32) or fs.value.upper()!='NTFS':
            raise RepositoryAccessError('Only tested local NTFS directory semantics supported')
        final=c.create_unicode_buffer(512);length=k.GetFinalPathNameByHandleW(handle,final,512,1)
        import re
        if not length or length>=512 or not re.fullmatch(r'\\\\\?\\Volume\{[0-9A-Fa-f-]+\}\\',final.value):
            raise RepositoryAccessError('Drive aliases or non-volume anchors are not admitted')
        return handle

    def _open_relative(self,parent,name):
        c,w,k,nt,Unicode,Attributes,IO,*_=self.api()
        encoded=name.encode('utf-16-le')
        if not encoded or len(encoded)>510 or any(char in name for char in ('\\','/',':','\0')):raise RepositoryAccessError('Invalid relative directory component')
        buffer=c.create_string_buffer(encoded+b'\0\0')
        string=Unicode(len(encoded),len(encoded)+2,c.cast(buffer,c.c_void_p))
        attrs=Attributes(c.sizeof(Attributes),parent,c.pointer(string),0x1040,None,None)
        status_block=IO();handle=w.HANDLE()
        # FILE_OPEN, DIRECTORY_FILE, SYNCHRONOUS_IO_NONALERT, OPEN_REPARSE_POINT.
        status=nt.NtCreateFile(c.byref(handle),0x100081,c.byref(attrs),c.byref(status_block),None,0,1,1,0x00200021,None,0)
        if status<0:
            code=nt.RtlNtStatusToDosError(status&0xffffffff)
            raise RepositoryAccessError('Native relative directory open denied: '+str(c.WinError(code)))
        return self._retain(handle.value)

    def __enter__(self):
        try:
            handle=self._open_anchor()
            # Walk the operator's root first, never a caller-supplied spelling
            # of that prefix. Every target component is then root-relative.
            for part in self.root.parts[1:]:handle=self._open_relative(handle,part)
            self.root_handle=handle
            parts=self.target.relative_to(self.root).parts
            for part in (parts[:-1] if self.is_file else parts):
                handle=self._open_relative(handle,part)
            self.target_handle=handle
            if self.is_file:self.file_handle=self._open_file(handle,parts[-1])
            return self
        except Exception:
            self.close();raise

    def close(self):
        if self.handles:
            k=self.api()[2]
            for handle in reversed(self.handles):k.CloseHandle(handle)
            self.handles=[]
        self.root_handle=None;self.target_handle=None;self.file_handle=None

    def __exit__(self,*args):self.close()

    def fingerprint(self,target=False):
        if target and self.is_file:return self.file_fingerprint()
        c,w,k,nt,Unicode,Attributes,IO,Basic,Identity,Entry=self.api()
        handle=self.target_handle if target else self.root_handle
        info=self._query(handle,0,Basic);identity=self._query(handle,18,Identity)
        if info.FileAttributes&0x400:raise RepositoryAccessError('Reparse directory binding invalid')
        value={'root':str(self.target if target else self.root),'device':int(identity.VolumeSerialNumber),
            'inode':int.from_bytes(bytes(identity.FileId),'little'),
            'mtime_ns':info.LastWriteTime*100-11644473600000000000,
            'ctime_ns':info.CreationTime*100-11644473600000000000}
        from hashlib import sha256
        return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

    def _open_file(self,parent,name):
        c,w,k,nt,Unicode,Attributes,IO,*_=self.api()
        encoded=name.encode('utf-16-le')
        if not encoded or len(encoded)>510 or any(x in name for x in ('\\','/',':','\0')):
            raise RepositoryAccessError('Invalid relative file component')
        buffer=c.create_string_buffer(encoded+b'\0\0');string=Unicode(len(encoded),len(encoded)+2,c.cast(buffer,c.c_void_p))
        attrs=Attributes(c.sizeof(Attributes),parent,c.pointer(string),0x1040,None,None)
        block=IO();handle=w.HANDLE()
        # Existing file only; NON_DIRECTORY_FILE, synchronous, OPEN_REPARSE_POINT.
        status=nt.NtCreateFile(c.byref(handle),0x100081,c.byref(attrs),c.byref(block),None,0,1,1,0x00200060,None,0)
        if status<0:raise RepositoryAccessError('Native relative file open denied: '+str(c.WinError(nt.RtlNtStatusToDosError(status&0xffffffff))))
        self.handles.append(handle.value)
        basic=self._query(handle.value,0,self.api()[7])
        if basic.FileAttributes&(0x400|0x10|0x40) or k.GetFileType(handle)!=1:
            raise RepositoryAccessError('Reparse, directory or non-disk file denied')
        self.file_handle=handle.value
        self.file_metadata()  # Reject hard links before any content access.
        return handle.value

    def file_metadata(self):
        c,w,*_=self.api()
        class Standard(c.Structure):
            _fields_=[('AllocationSize',c.c_longlong),('EndOfFile',c.c_longlong),('NumberOfLinks',w.DWORD),('DeletePending',c.c_ubyte),('Directory',c.c_ubyte)]
        if c.sizeof(Standard)!=24:raise RepositoryAccessError('Unexpected file metadata ABI')
        standard=self._query(self.file_handle,1,Standard)
        if standard.Directory or standard.DeletePending or standard.NumberOfLinks!=1 or standard.EndOfFile<0:
            raise RepositoryAccessError('Only stable single-link regular files admitted')
        return standard

    def file_fingerprint(self):
        standard=self.file_metadata();basic=self._query(self.file_handle,0,self.api()[7]);identity=self._query(self.file_handle,18,self.api()[8])
        if basic.FileAttributes&0x400:raise RepositoryAccessError('File became a reparse point')
        value={'path':str(self.target),'volume':int(identity.VolumeSerialNumber),'file_id':bytes(identity.FileId).hex(),
            'size':standard.EndOfFile,'creation':basic.CreationTime,'write':basic.LastWriteTime,'change':basic.ChangeTime,'links':standard.NumberOfLinks}
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def read_bytes(self,limit):
        if type(limit) is not int or not 1<=limit<=16384:raise RepositoryAccessError('Bounded file content limit required')
        size=self.file_metadata().EndOfFile
        if size>limit:raise RepositoryAccessError('File exceeds authorized byte limit')
        before=self.file_fingerprint();c,w,k,*_=self.api();buffer=c.create_string_buffer(limit+1);count=w.DWORD()
        if not k.ReadFile(self.file_handle,buffer,limit+1,c.byref(count),None):
            raise RepositoryAccessError('Retained file read failed: '+str(c.WinError(c.get_last_error())))
        if count.value!=size or count.value>limit or self.file_fingerprint()!=before:
            raise RepositoryAccessError('File changed or bounded read incomplete')
        return buffer.raw[:count.value]

    def records(self):
        if self.is_file:raise RepositoryAccessError('File binding cannot enumerate directories')
        if self.target_handle is None or self.target_handle not in self.handles:raise RepositoryAccessError('Directory binding is closed')
        c,w,k,nt,Unicode,Attributes,IO,Basic,Identity,Entry=self.api();first=True
        while True:
            if self.target_handle not in self.handles:raise RepositoryAccessError('Directory binding is closed')
            buffer=c.create_string_buffer(65536)
            if not k.GetFileInformationByHandleEx(self.target_handle,11 if first else 10,buffer,len(buffer)):
                error=c.get_last_error()
                if error==18:return
                raise RepositoryAccessError('Handle directory enumeration denied: '+str(c.WinError(error)))
            first=False;offset=0;raw=buffer.raw
            while True:
                if offset+Entry.FileName.offset>len(raw):raise RepositoryAccessError('Malformed native directory record')
                record=Entry.from_buffer_copy(raw,offset);length=record.FileNameLength
                if not length or length%2 or offset+104+length>len(raw):raise RepositoryAccessError('Malformed native filename')
                name=raw[offset+104:offset+104+length].decode('utf-16-le','strict')
                if name not in ('.','..'):
                    if self.target_handle not in self.handles:raise RepositoryAccessError('Directory binding is closed')
                    if any(char in name for char in ('\\','/',':','\0')):raise RepositoryAccessError('Unsafe native filename')
                    yield {'name':name,'attributes':int(record.FileAttributes),'size':int(record.EndOfFile),'file_id':int(record.FileId)&0xffffffffffffffff}
                step=record.NextEntryOffset
                if not step:break
                if step%8 or step<104+length or offset+step>=len(raw):raise RepositoryAccessError('Malformed native record chain')
                offset+=step


class RepositoryReader:
    MAX_READ_BYTES=16384
    MAX_READ_CHARS=8192
    BLOCKED_NAMES = {
        ".env",
        ".git",
        "__pycache__",
    }

    BLOCKED_SUFFIXES = {
        ".pem",
        ".key",
        ".pfx",
        ".p12",
        ".sqlite",
        ".db",
        ".zip",
        ".exe",
        ".dll",
        ".bin",
    }

    TEXT_SUFFIXES = {
        ".py",
        ".txt",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".sql",
        ".csv",
        ".html",
        ".css",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".bat",
        ".ps1",
    }

    def __init__(self, repository_root: str) -> None:
        self.root=WindowsDirectoryBinding.lexical(repository_root)
        with WindowsDirectoryBinding(self.root):pass

    def _lexical_source(self,value):
        raw=Path(value)
        target=raw if raw.is_absolute() else self.root/raw
        target=WindowsDirectoryBinding.lexical(target)
        try:target.relative_to(self.root)
        except ValueError as exc:raise RepositoryAccessError('path escapes repository root') from exc
        return target

    @staticmethod
    def _unlinked(path):
        for node in [path,*path.parents]:
            if node.is_symlink() or node.is_junction():
                raise RepositoryAccessError('Linked repository path denied')

    def _resolve(self, relative_path: str = '') -> Path:
        if not isinstance(relative_path,str):raise RepositoryAccessError('relative_path must be a string')
        raw=Path(relative_path.strip())
        if '..' in raw.parts or any(':' in part for part in raw.parts if part!=raw.anchor) or (bool(raw.drive) and not raw.is_absolute()):
            raise RepositoryAccessError('Traversal or alternate stream denied')
        candidate=self.root if not relative_path.strip() else self.root/raw
        try:candidate.relative_to(self.root)
        except ValueError as exc:raise RepositoryAccessError('path escapes repository root') from exc
        self._unlinked(candidate)
        candidate=candidate.resolve()
        try:candidate.relative_to(self.root)
        except ValueError as exc:raise RepositoryAccessError('path escapes repository root') from exc
        return candidate

    def _assert_not_blocked(self, path: Path) -> None:
        relative_parts = path.relative_to(self.root).parts

        for part in relative_parts:
            if part in self.BLOCKED_NAMES:
                raise RepositoryAccessError(
                    f"blocked repository path: {part}"
                )

        if path.suffix.lower() in self.BLOCKED_SUFFIXES:
            raise RepositoryAccessError(
                f"blocked file type: {path.suffix}"
            )

    def list_directory(self, relative_path: str = '', *, max_entries: int = 256) -> dict[str, Any]:
        """Enumerate only a pinned Windows directory; never stat child paths."""
        target=self._lexical_source(relative_path or str(self.root));self._assert_not_blocked(target)
        with WindowsDirectoryBinding(self.root,target) as binding:
            return self._list_bound(binding,max_entries)

    def _list_bound(self,binding,max_entries):
        if type(max_entries) is not int or not 1<=max_entries<=256:raise RepositoryAccessError('Bounded directory listing required')
        entries=[];excluded=[];examined=0
        for record in binding.records():
            examined+=1
            if examined>max_entries:raise RepositoryAccessError('Directory listing bound exceeded')
            name=record['name'];child=binding.target/name
            try:self._assert_not_blocked(child)
            except RepositoryAccessError:
                excluded.append({'name':name,'reason':'PROTECTED_REPOSITORY_PATH'});continue
            if record['attributes']&0x400:
                excluded.append({'name':name,'reason':'LINK_NOT_FOLLOWED'});continue
            directory=bool(record['attributes']&0x10)
            entries.append({'name':name,'path':str(child.relative_to(self.root)),
                'type':'directory' if directory else 'file','size':None if directory else record['size']})
        entries.sort(key=lambda item:(item['type']!='directory',item['name'].lower()))
        return {'root':str(self.root),'path':str(binding.target.relative_to(self.root)),'entries':entries,
            'excluded':excluded,'recursive':False,'source_contents_read':False,'examined_entries':examined,
            'containment':'WINDOWS_NTFS_RETAINED_RELATIVE_DIRECTORY_HANDLES/1'}

    def _read_bound(self,binding,max_bytes,max_chars):
        self._assert_not_blocked(binding.target)
        if any(part.casefold() in {x.casefold() for x in self.BLOCKED_NAMES} for part in binding.target.relative_to(self.root).parts):
            raise RepositoryAccessError('Protected file path denied')
        if binding.target.suffix.lower() not in self.TEXT_SUFFIXES:
            raise RepositoryAccessError('File format not admitted for governed text reading')
        if type(max_chars) is not int or not 1<=max_chars<=self.MAX_READ_CHARS:
            raise RepositoryAccessError('Bounded character limit required')
        raw=binding.read_bytes(max_bytes)
        try:text=raw.decode('utf-8-sig','strict')
        except UnicodeError as exc:raise RepositoryAccessError('File is not strict UTF-8 text') from exc
        if any(ord(ch)<32 and ch not in '\r\n\t' or ord(ch)==127 for ch in text):
            raise RepositoryAccessError('Binary/control content not admitted')
        if len(text)>max_chars:raise RepositoryAccessError('File exceeds authorized character limit')
        return {'path':str(binding.target.relative_to(self.root)),'content':text,'size':len(raw),
            'content_sha256':hashlib.sha256(raw).hexdigest(),'file_fingerprint':binding.fingerprint(True),
            'encoding':'utf-8-sig','truncated':False,'source_contents_read':True,'evidence_state':'OBSERVED',
            'claim_validation':'NOT_ESTABLISHED','containment':'WINDOWS_NTFS_RETAINED_RELATIVE_FILE_HANDLES/1'}

    def execute_confirmed_inspection(self, action, outcome, *, process, operator_id,
            thread_id, objective, grant_path):
        """One signed, current, operator-scoped metadata read via existing listing.

        This guard grants no write/shell/content-read interface. The operator
        provisions policy; model proposals cannot provision or amend approvals.
        """
        from system_layer.contracts import authorize,digest
        started=False
        try:
            request=outcome['request'];scope=request['scope']
            verified=process.client.verify_response(request,outcome['response'])
            if not verified['accepted'] or request['request_id'] not in process.client._used:
                raise RepositoryAccessError('Confirmed consumed RP request required')
            if type(action) is not dict or set(action)!={'operation','source','destination','rationale'} or action['operation'] not in {'INSPECT_DIRECTORY','READ_FILE'} or action['destination'] is not None:
                raise RepositoryAccessError('Only exact read-only inspection may execute')
            file=action['operation']=='READ_FILE'
            source=self._lexical_source(action['source']);self._assert_not_blocked(source)
            normalized={**action,'source':str(source)}
            if digest(normalized)!=scope['action_hash']:raise RepositoryAccessError('Approved action hash mismatch')
            claim=request['evaluation']['resolution']['claim_snapshot']
            if claim['source_specification']['action']!=normalized:raise RepositoryAccessError('Approved action substituted')
            def current(binding=None):
                grant=json.loads(Path(grant_path).read_text(encoding='utf-8'))
                if digest(grant)!=claim['provenance']['grant_hash'] or digest({k:v for k,v in grant.items() if k!='evidence'})!=scope['grant_hash']:
                    raise RepositoryAccessError('Inspection grant changed')
                policy=grant['inspection_authorization']['request']
                authorize(operator_id,'OBJECTIVE_READ_ONLY_INSPECTION',policy,grant['inspection_authorization']['approval'])
                if grant['control']!='ACTIVE' or datetime.now(timezone.utc)>datetime.fromisoformat(grant['valid_until']):
                    raise RepositoryAccessError('Inspection grant stale or revoked')
                if any(grant[k]!=value or scope[k]!=value for k,value in [('operator_id',operator_id),('thread_id',thread_id),('objective_hash',digest(objective))]):
                    raise RepositoryAccessError('Inspection owner/objective mismatch')
                if any(policy[k]!=grant[k] for k in ('operator_id','thread_id','objective_hash','root','valid_until')):
                    raise RepositoryAccessError('Operator inspection policy mismatch')
                expected_contract='RepositoryReader.read_bound/1' if file else 'RepositoryReader.list_directory/1'
                allowed=policy.get('operations',[policy['operation']])
                if (action['operation'] not in allowed or policy['operation'] not in {'INSPECT_DIRECTORY','READ_ONLY_OBSERVATION'} or policy['recursive'] is not False or
                        type(policy['max_entries']) is not int or not 1<=policy['max_entries']<=256 or
                        scope['inspection_contract']!=expected_contract or
                        self.root!=WindowsDirectoryBinding.lexical(grant['root']) or str(self.root)!=scope['workspace']):
                    raise RepositoryAccessError('Inspection operation or root not authorized')
                if file and (set(policy)-{'operator_id','thread_id','objective_hash','root','operation','executor_path','executor_sha256','collector_sha256','max_entries','recursive','valid_until'}!={'operations','max_bytes','max_chars'}
                        or type(policy['max_bytes']) is not int or not 1<=policy['max_bytes']<=self.MAX_READ_BYTES
                        or type(policy['max_chars']) is not int or not 1<=policy['max_chars']<=self.MAX_READ_CHARS):
                    raise RepositoryAccessError('Explicit bounded file-read policy required')
                own=Path(__file__).resolve()
                if (Path(policy['executor_path']).resolve()!=own or hashlib.sha256(own.read_bytes()).hexdigest()!=policy['executor_sha256'] or
                        scope['executor_hash']!=policy['executor_sha256'] or scope['collector_hash']!=policy['collector_sha256']):
                    raise RepositoryAccessError('Executor/collector version changed')
                if binding is not None:
                    if binding.fingerprint()!=scope['workspace_hash'] or binding.fingerprint(True)!=scope['inspection_target_hash']:
                        raise RepositoryAccessError('Approved directory identity or freshness changed')
                u=claim['source_understanding']
                with sqlite3.connect(Path(grant['understanding_store']).resolve().as_uri()+'?mode=ro',uri=True) as db:
                    row=db.execute('SELECT payload,bundle,checksum FROM versions WHERE operator_id=? AND understanding_id=? AND version=?',(operator_id,scope['understanding_id'],scope['understanding_version'])).fetchone()
                    head=db.execute('SELECT version FROM heads WHERE operator_id=? AND thread_id=? AND understanding_id=?',(operator_id,thread_id,scope['understanding_id'])).fetchone()
                if not row or not head or head[0]!=scope['understanding_version'] or digest(json.loads(row[0]))!=scope['understanding_hash'] or digest(u)!=scope['understanding_hash']:
                    raise RepositoryAccessError('Current Understanding differs from confirmation')
                checksum=hashlib.sha256(json.dumps({'record':json.loads(row[0]),'bundle':json.loads(row[1])},sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
                if checksum!=row[2]:raise RepositoryAccessError('Understanding source integrity invalid')
                return policy
            policy=current()
            with WindowsDirectoryBinding(self.root,source,file=file) as binding:
                current(binding)
                check=process.call('current',{'request_id':request['request_id'],'scope':scope})
                if check!={'current':True,'scope_hash':digest(scope)}:raise RepositoryAccessError('Current scope check unavailable')
                lease=process.call('claim_execution',{'request_id':request['request_id'],'scope':scope})
                if lease!={'claimed':True,'request_id':request['request_id'],'scope_hash':digest(scope)}:raise RepositoryAccessError('Single-use execution claim unavailable')
                current(binding);started=True
                result=self._read_bound(binding,policy['max_bytes'],policy['max_chars']) if file else self._list_bound(binding,policy['max_entries'])
                current(binding)
                process.call('current',{'request_id':request['request_id'],'scope':scope})
            return {'contract':'AuthorizedFileRead/1' if file else 'AuthorizedDirectoryInspection/1','request_id':request['request_id'],
                'rp_receipt_id':verified['receipt_id'],'operator_id':operator_id,'thread_id':thread_id,
                'action':normalized,'action_hash':scope['action_hash'],'state':'READ_ONLY_FILE_RETURNED' if file else 'READ_ONLY_INSPECTION_RETURNED',
                'findings':result,'action_executed':True,'objective_completion_established':False,'timestamp':datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            error=RepositoryAccessError(str(exc));error.inspection_started=started
            raise error from exc

    def read_file(
        self,
        relative_path: str,
        *,
        max_chars: int = 200_000,
    ) -> dict[str, Any]:
        path = self._resolve(relative_path)
        self._assert_not_blocked(path)

        if not path.exists():
            raise RepositoryAccessError("file does not exist")

        if not path.is_file():
            raise RepositoryAccessError("path is not a file")

        if path.suffix.lower() not in self.TEXT_SUFFIXES:
            raise RepositoryAccessError(
                "file type is not approved for text reading"
            )

        content = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        truncated = len(content) > max_chars

        if truncated:
            content = content[:max_chars]

        return {
            "path": str(path.relative_to(self.root)),
            "content": content,
            "truncated": truncated,
            "size": path.stat().st_size,
        }

    def search(
        self,
        query: str,
        *,
        relative_path: str = "",
        max_results: int = 100,
    ) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise RepositoryAccessError(
                "query must be a non-empty string"
            )

        base = self._resolve(relative_path)
        self._assert_not_blocked(base)

        if not base.exists():
            raise RepositoryAccessError("search path does not exist")

        results = []
        needle = query.lower()

        files = (
            [base]
            if base.is_file()
            else base.rglob("*")
        )

        for path in files:
            if len(results) >= max_results:
                break

            if not path.is_file():
                continue

            try:
                self._assert_not_blocked(path)
            except RepositoryAccessError:
                continue

            if path.suffix.lower() not in self.TEXT_SUFFIXES:
                continue

            try:
                text = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            for line_number, line in enumerate(
                text.splitlines(),
                start=1,
            ):
                if needle in line.lower():
                    results.append(
                        {
                            "path": str(
                                path.relative_to(self.root)
                            ),
                            "line": line_number,
                            "text": line[:1000],
                        }
                    )

                    if len(results) >= max_results:
                        break

        return {
            "query": query,
            "search_root": str(
                base.relative_to(self.root)
            ),
            "results": results,
            "result_count": len(results),
        }

    def git_status(self) -> dict[str, Any]:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.root,
            capture_output=True,
            text=True,
            shell=False,
            timeout=15,
        )

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def git_diff(self) -> dict[str, Any]:
        result = subprocess.run(
            ["git", "diff", "--no-ext-diff"],
            cwd=self.root,
            capture_output=True,
            text=True,
            shell=False,
            timeout=15,
        )

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
