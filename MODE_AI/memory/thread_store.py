import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from memory.thread_memory import ThreadMemory
from data_governance.custody_json import load as load_custody_json


@contextmanager
def _writer_guard(path,error_prefix='THREAD_WRITE_CONFLICT'):
    """Cooperative, process-scoped writer exclusion; not a Kernel trust anchor."""
    with path.with_suffix('.lock').open('a+b') as lock:
        lock.seek(0,os.SEEK_END)
        if lock.tell()==0:
            lock.write(b'\0');lock.flush()
        lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError(error_prefix+': another writer is active') from exc
        try:yield
        finally:
            lock.seek(0)
            if os.name=='nt':msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


class ThreadStore:
    def __init__(self, storage_dir: str = "data/threads") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _operator_dir(self, operator_id: str) -> Path:
        self._validate_identity(operator_id)
        path = self.storage_dir / operator_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _thread_path(self, operator_id: str, thread_id: str) -> Path:
        self._validate_identity(thread_id)
        return self._operator_dir(operator_id) / f"{thread_id}.json"

    @staticmethod
    def _validate_identity(identity: str) -> None:
        if (type(identity) is not str or not identity.strip() or identity in {'.', '..'}
                or identity != identity.strip() or identity.endswith('.')
                or any(c in identity for c in '/\\:<>"|?*') or any(ord(c)<32 for c in identity)
                or identity.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}):
            raise ValueError('Thread custody requires a single nonempty identity component')

    def create_thread(self, operator_id: str, title: str = "New Thread") -> ThreadMemory:
        thread = ThreadMemory.create(operator_id=operator_id, title=title)
        self.save_thread(thread)
        return thread

    def create_from_request(self,operator_id,request,approval):
        from system_layer.contracts import authorize,digest
        if type(request) is not dict or set(request)!={'title'} or type(request['title']) is not str or not request['title'].strip() or len(request['title'])>256:
            raise ValueError('A bounded explicit conversation title is required')
        authorize(operator_id,'THREAD_CREATE',request,approval)
        thread=ThreadMemory.create(operator_id,request['title']);thread.is_active=False
        self.save_thread(thread)
        return {'contract':'ThreadCreation/1','thread':thread.to_dict(),'thread_hash':digest(thread.to_dict()),
            'active_thread_changed':False,'vault_preserved':False,'execution_authority':False}

    def fork_thread(self,operator_id,request,approval):
        from copy import deepcopy
        from system_layer.contracts import authorize,digest
        if type(request) is not dict or set(request)!={'source_thread_id','expected_source_hash','project_id','title'}:
            raise ValueError('Exact thread fork request required')
        authorize(operator_id,'THREAD_FORK',request,approval)
        if any(type(request[k]) is not str or not request[k].strip() for k in request):
            raise ValueError('Explicit thread lineage required')
        parent=self.load_thread(operator_id,request['source_thread_id']);snapshot=parent.to_dict()
        if digest(snapshot)!=request['expected_source_hash']:raise ValueError('Thread source changed before fork')
        if parent.continuity and parent.continuity['project_id']!=request['project_id']:
            raise PermissionError('Cross-project thread fork requires separate source selection')
        child=ThreadMemory.create(operator_id,request['title']);child.messages=deepcopy(parent.messages);child.is_active=False
        child.continuity={'schema_version':'ThreadContinuity/1','project_id':request['project_id'],
            'parent_thread_id':parent.thread_id,'parent_snapshot_hash':request['expected_source_hash'],
            'inherited_count':len(parent.messages),'inherited_messages_hash':digest(snapshot['messages'])}
        self.save_thread(child)
        return {'contract':'ThreadFork/1','thread':child.to_dict(),'thread_hash':digest(child.to_dict()),
                'active_thread_changed':False,'vault_preserved':False,'claims_validated':False}

    def save_thread(self, thread: ThreadMemory) -> None:
        from system_layer.contracts import digest
        path = self._thread_path(thread.operator_id, thread.thread_id)
        data=thread.to_dict()
        ThreadMemory.from_dict(data)
        # A failed serialization or write must not truncate the previous thread.
        payload=json.dumps(data,indent=2,allow_nan=False)
        with _writer_guard(path):
            expected=getattr(thread,'_custody_baseline',None)
            current=self.load_thread(thread.operator_id,thread.thread_id) if path.exists() else None
            actual=getattr(current,'_custody_baseline',None)
            if actual!=expected:
                thread._custody_conflict=True
                raise ValueError('THREAD_WRITE_CONFLICT: persisted conversation changed; explicit reload required')
            temporary=None
            try:
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                                 prefix=path.stem+'.',suffix='.tmp',delete=False) as file:
                    temporary=Path(file.name)
                    file.write(payload);file.flush();os.fsync(file.fileno())
                os.replace(temporary,path)
                thread._custody_baseline=digest(data)
                thread._custody_conflict=False
            finally:
                if temporary is not None and temporary.exists():temporary.unlink()

    def load_thread(self, operator_id: str, thread_id: str) -> ThreadMemory:
        path = self._thread_path(operator_id, thread_id)

        if not path.exists():
            raise FileNotFoundError(
                f"No thread found for operator={operator_id}, thread={thread_id}"
            )

        with path.open("r", encoding="utf-8") as file:
            data = load_custody_json(file)

        thread = ThreadMemory.from_dict(data)

        if thread.operator_id != operator_id or thread.thread_id != thread_id:
            raise PermissionError("Thread crossover blocked.")
        from system_layer.contracts import digest
        thread._custody_baseline=digest(data)
        return thread

    def list_threads(self, operator_id: str) -> List[ThreadMemory]:
        operator_dir = self._operator_dir(operator_id)
        threads: List[ThreadMemory] = []

        for path in operator_dir.glob("*.json"):
            threads.append(self.load_thread(operator_id, path.stem))

        return sorted(threads, key=lambda thread: thread.updated_at, reverse=True)

    def get_or_create_active_thread(
        self,
        operator_id: str,
        thread_id: Optional[str] = None,
    ) -> ThreadMemory:
        if thread_id:
            return self.load_thread(operator_id=operator_id, thread_id=thread_id)

        threads = self.list_threads(operator_id)

        for thread in threads:
            if thread.is_active:
                return thread

        return self.create_thread(operator_id=operator_id)
