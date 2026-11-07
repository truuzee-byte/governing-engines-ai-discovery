from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ThreadReference:
    thread_id: str
    title: str = "New Thread"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    summary: str = ""


@dataclass
class OperatorManagedInfo:
    name: str = ""
    preferred_name: str = ""
    timezone: str = ""
    language: str = ""


@dataclass
class SystemObservedEvidence:
    communication_patterns: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_patterns: List[Dict[str, Any]] = field(default_factory=list)
    clarification_preferences: List[Dict[str, Any]] = field(default_factory=list)
    evidence_expectations: List[Dict[str, Any]] = field(default_factory=list)
    interaction_style: List[Dict[str, Any]] = field(default_factory=list)
    constraint_patterns: List[Dict[str, Any]] = field(default_factory=list)
    historical_observations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OperatorProfile:
    operator_id: str
    operator_managed: OperatorManagedInfo = field(default_factory=OperatorManagedInfo)
    system_observed: SystemObservedEvidence = field(default_factory=SystemObservedEvidence)

    active_thread_id: Optional[str] = None
    thread_index: List[ThreadReference] = field(default_factory=list)
    continuity_summary: str = ""

    onboarding_complete: bool = False
    profile_version: str = "0.2"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def required_onboarding_fields_missing(self) -> List[str]:
        missing = []

        if not self.operator_managed.preferred_name.strip():
            missing.append("preferred_name")

        if not self.operator_managed.timezone.strip():
            missing.append("timezone")

        if not self.operator_managed.language.strip():
            missing.append("language")

        return missing

    def is_onboarding_complete(self) -> bool:
        return len(self.required_onboarding_fields_missing()) == 0

    def update_operator_managed_info(
        self,
        preferred_name: Optional[str] = None,
        timezone: Optional[str] = None,
        language: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        if name is not None:
            self.operator_managed.name = name.strip()

        if preferred_name is not None:
            self.operator_managed.preferred_name = preferred_name.strip()

        if timezone is not None:
            self.operator_managed.timezone = timezone.strip()

        if language is not None:
            self.operator_managed.language = language.strip()

        self.onboarding_complete = self.is_onboarding_complete()
        self.touch()

    def set_active_thread(self, thread_id: str) -> None:
        self.active_thread_id = thread_id
        self.touch()

    def upsert_thread_reference(
        self,
        thread_id: str,
        title: str = "New Thread",
        summary: str = "",
    ) -> None:
        for thread_ref in self.thread_index:
            if thread_ref.thread_id == thread_id:
                thread_ref.title = title
                thread_ref.summary = summary or thread_ref.summary
                thread_ref.updated_at = utc_now()
                self.touch()
                return

        self.thread_index.append(
            ThreadReference(
                thread_id=thread_id,
                title=title,
                summary=summary,
            )
        )
        self.touch()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OperatorProfile":
        if type(data) is not dict or set(data)!=set(OperatorProfile.__dataclass_fields__):
            raise ValueError('PROFILE_INTEGRITY_FAILURE: incomplete or unknown persisted fields')
        for key in ('operator_id','created_at','updated_at','profile_version'):
            if type(data[key]) is not str or not data[key].strip():raise ValueError('PROFILE_INTEGRITY_FAILURE: identity/version/timestamp unavailable')
        if type(data['continuity_summary']) is not str or type(data['onboarding_complete']) is not bool:
            raise ValueError('PROFILE_INTEGRITY_FAILURE: malformed continuity state')
        if data['active_thread_id'] is not None and (type(data['active_thread_id']) is not str or not data['active_thread_id'].strip()):
            raise ValueError('PROFILE_INTEGRITY_FAILURE: malformed active thread')
        for key,model in (('operator_managed',OperatorManagedInfo),('system_observed',SystemObservedEvidence)):
            if type(data[key]) is not dict or set(data[key])!=set(model.__dataclass_fields__):
                raise ValueError('PROFILE_INTEGRITY_FAILURE: incomplete '+key)
        if any(type(v) is not str for v in data['operator_managed'].values()):
            raise ValueError('PROFILE_INTEGRITY_FAILURE: malformed Operator answers')
        if any(type(v) is not list or any(type(item) is not dict for item in v) for v in data['system_observed'].values()):
            raise ValueError('PROFILE_INTEGRITY_FAILURE: malformed observed evidence')
        if type(data['thread_index']) is not list or any(type(v) is not dict or set(v)!=set(ThreadReference.__dataclass_fields__)
                or any(type(item) is not str for item in v.values()) for v in data['thread_index']):
            raise ValueError('PROFILE_INTEGRITY_FAILURE: malformed thread index')
        return OperatorProfile(
            operator_id=data["operator_id"],
            operator_managed=OperatorManagedInfo(**data.get("operator_managed", {})),
            system_observed=SystemObservedEvidence(**data.get("system_observed", {})),
            active_thread_id=data.get("active_thread_id"),
            thread_index=[
                ThreadReference(**thread_ref)
                for thread_ref in data.get("thread_index", [])
            ],
            continuity_summary=data.get("continuity_summary", ""),
            onboarding_complete=data.get("onboarding_complete", False),
            profile_version=data.get("profile_version", "0.2"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )
