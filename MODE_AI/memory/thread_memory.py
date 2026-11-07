from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ThreadMessage:
    message_id: str
    role: str
    content: str
    created_at: str = field(default_factory=utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def create(role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> "ThreadMessage":
        return ThreadMessage(
            message_id=f"message-{uuid4().hex}",
            role=role,
            content=content,
            metadata=metadata or {},
        )


@dataclass
class ThreadMemory:
    thread_id: str
    operator_id: str
    title: str = "New Thread"
    messages: List[ThreadMessage] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    is_active: bool = True
    continuity: Optional[Dict[str, Any]] = None
    halt: Optional[Dict[str, Any]] = None

    @staticmethod
    def create(operator_id: str, title: str = "New Thread") -> "ThreadMemory":
        return ThreadMemory(
            thread_id=f"thread-{uuid4().hex}",
            operator_id=operator_id,
            title=title,
        )

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> ThreadMessage:
        message = ThreadMessage.create(role=role, content=content, metadata=metadata)
        self.messages.append(message)
        self.updated_at = utc_now()
        return message

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.continuity is None:data.pop('continuity')
        if self.halt is None:data.pop('halt')
        return data

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ThreadMemory":
        required={'thread_id','operator_id','title','messages','created_at','updated_at','is_active'}
        if type(data) is not dict or not required.issubset(data) or set(data)-required-{'continuity','halt'}:
            raise ValueError('THREAD_INTEGRITY_FAILURE: incomplete or unknown thread fields')
        for name in ('thread_id','operator_id','created_at','updated_at'):
            if type(data[name]) is not str or not data[name].strip():
                raise ValueError('THREAD_INTEGRITY_FAILURE: missing identity or timestamp')
        if type(data['title']) is not str or type(data['is_active']) is not bool or type(data['messages']) is not list:
            raise ValueError('THREAD_INTEGRITY_FAILURE: malformed thread state')
        seen=set()
        for message in data['messages']:
            if type(message) is not dict or set(message)!={'message_id','role','content','created_at','metadata'}:
                raise ValueError('THREAD_INTEGRITY_FAILURE: incomplete message')
            if any(type(message[key]) is not str for key in ('message_id','role','content','created_at')):
                raise ValueError('THREAD_INTEGRITY_FAILURE: malformed message text')
            if (not message['message_id'] or not message['role'] or not message['created_at']
                    or message['message_id'] in seen or type(message['metadata']) is not dict):
                raise ValueError('THREAD_INTEGRITY_FAILURE: malformed message lineage')
            seen.add(message['message_id'])
        continuity=data.get('continuity')
        if 'continuity' in data:
            from system_layer.contracts import digest
            if type(continuity) is not dict or set(continuity)!={'schema_version','project_id','parent_thread_id','parent_snapshot_hash','inherited_count','inherited_messages_hash'}:
                raise ValueError('THREAD_INTEGRITY_FAILURE: malformed continuity')
            if continuity['schema_version']!='ThreadContinuity/1' or any(type(continuity[k]) is not str or not continuity[k] for k in ('project_id','parent_thread_id','parent_snapshot_hash','inherited_messages_hash')):
                raise ValueError('THREAD_INTEGRITY_FAILURE: missing continuity lineage')
            count=continuity['inherited_count']
            if type(count) is not int or count<0 or count>len(data['messages']) or digest(data['messages'][:count])!=continuity['inherited_messages_hash']:
                raise ValueError('THREAD_INTEGRITY_FAILURE: inherited conversation changed')
        halt = data.get('halt')
        if halt is not None:
            if (type(halt) is not dict or set(halt) != {'halt_id','operator_id','thread_id','created_at'}
                    or any(type(v) is not str or not v for v in halt.values())
                    or halt['operator_id'] != data['operator_id'] or halt['thread_id'] != data['thread_id']):
                raise ValueError('THREAD_INTEGRITY_FAILURE: malformed halt custody')
        return ThreadMemory(
            thread_id=data["thread_id"],
            operator_id=data["operator_id"],
            title=data["title"],
            messages=[
                ThreadMessage(**message)
                for message in data["messages"]
            ],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            is_active=data["is_active"],
            continuity=continuity,
            halt=halt,
        )
