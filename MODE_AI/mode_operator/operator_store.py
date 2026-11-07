import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from mode_operator.operator_identity import OperatorIdentity
from mode_operator.operator_profile import OperatorProfile
from memory.thread_store import _writer_guard
from system_layer.contracts import digest
from data_governance.custody_json import load as load_custody_json


@dataclass
class OperatorProfileSummary:
    operator_id: str
    display_name: str
    preferred_name: str
    timezone: str
    language: str
    onboarding_complete: bool
    updated_at: str


class OperatorStore:
    def __init__(self, storage_dir: str = "data/operators") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _profile_path(self, operator_id: str) -> Path:
        from memory.thread_store import ThreadStore
        ThreadStore._validate_identity(operator_id)
        if operator_id=='current_operator':raise ValueError('Reserved Operator identity')
        return self.storage_dir / f"{operator_id}.json"

    @staticmethod
    def _write_json(path, data):
        payload=json.dumps(data,indent=2,allow_nan=False)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                    prefix=path.stem+'.',suffix='.tmp',delete=False) as file:
                temporary=Path(file.name);file.write(payload);file.flush();os.fsync(file.fileno())
            os.replace(temporary,path)
        finally:
            if temporary is not None and temporary.exists():temporary.unlink()

    def select_active_thread(self,identity,thread_id,expected_profile):
        """Persist only the approved thread selection; do not overwrite stale profile data."""
        from memory.thread_store import ThreadStore
        from system_layer.contracts import digest
        ThreadStore._validate_identity(thread_id)
        path=self._profile_path(identity.operator_id)
        with _writer_guard(path,'PROFILE_WRITE_CONFLICT'):
            profile=self.load_profile(identity)
            if digest(profile.to_dict())!=digest(expected_profile):raise ValueError('Operator profile changed before thread selection')
            profile.active_thread_id=thread_id;profile.touch()
            self._write_json(path,profile.to_dict())
            profile._custody_baseline=digest(profile.to_dict())
        return profile

    def save_profile_if_current(self,identity,profile,expected_hash):
        from system_layer.contracts import digest
        identity.require_profile_match(profile.operator_id)
        path=self._profile_path(identity.operator_id)
        with _writer_guard(path,'PROFILE_WRITE_CONFLICT'):
            current=self.load_profile(identity)
            if digest(current.to_dict())!=expected_hash:
                raise ValueError('Operator profile changed before update')
            profile.touch()
            OperatorProfile.from_dict(profile.to_dict())
            self._write_json(path,profile.to_dict())
            profile._custody_baseline=digest(profile.to_dict())

    def _current_operator_path(self) -> Path:
        return self.storage_dir / "current_operator.json"

    def get_current_operator_id(self) -> Optional[str]:
        path = self._current_operator_path()

        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as file:
            data = load_custody_json(file)
        if type(data) is not dict or set(data)!={'operator_id'}:
            raise ValueError('PROFILE_SELECTION_INTEGRITY_FAILURE')
        if not self._profile_path(data['operator_id']).is_file():
            raise FileNotFoundError('Selected Operator profile is unavailable; no replacement created')
        return data['operator_id']

    def set_current_operator_id(self, operator_id: str) -> None:
        self._profile_path(operator_id)
        path = self._current_operator_path()
        with _writer_guard(path,'PROFILE_SELECTION_CONFLICT'):
            self._write_json(path,{"operator_id":operator_id})

    def clear_current_operator_id(self) -> None:
        path = self._current_operator_path()

        if path.exists():
            path.unlink()

    def profile_exists(self, operator_id: str) -> bool:
        return self._profile_path(operator_id).exists()

    def list_profile_ids(self) -> List[str]:
        profile_ids: List[str] = []

        for path in self.storage_dir.glob("*.json"):
            if path.name=='current_operator.json':continue
            profile_ids.append(path.stem)

        return sorted(profile_ids)

    def list_profiles(self) -> List[OperatorProfileSummary]:
        summaries: List[OperatorProfileSummary] = []

        for operator_id in self.list_profile_ids():
            try:
                identity = OperatorIdentity.create(operator_id=operator_id)
                profile = self.load_profile(identity)
                managed = profile.operator_managed

                display_name = (
                    managed.preferred_name
                    or managed.name
                    or profile.operator_id
                )

                summaries.append(
                    OperatorProfileSummary(
                        operator_id=profile.operator_id,
                        display_name=display_name,
                        preferred_name=managed.preferred_name,
                        timezone=managed.timezone,
                        language=managed.language,
                        onboarding_complete=profile.is_onboarding_complete(),
                        updated_at=profile.updated_at,
                    )
                )
            except Exception as exc:
                raise ValueError('Operator profile listing incomplete: '+operator_id) from exc

        return sorted(
            summaries,
            key=lambda summary: summary.updated_at,
            reverse=True,
        )

    def create_profile(self, identity: OperatorIdentity) -> OperatorProfile:
        if self.profile_exists(identity.operator_id):
            return self.load_profile(identity)

        profile = OperatorProfile(operator_id=identity.operator_id)
        self.save_profile(identity, profile)
        self.set_current_operator_id(identity.operator_id)
        return profile

    def load_profile(self, identity: OperatorIdentity) -> OperatorProfile:
        path = self._profile_path(identity.operator_id)

        if not path.exists():
            raise FileNotFoundError(f"No operator profile found for {identity.operator_id}")

        with path.open("r", encoding="utf-8") as file:
            data = load_custody_json(file)

        profile = OperatorProfile.from_dict(data)
        identity.require_profile_match(profile.operator_id)
        profile._custody_baseline=digest(data)
        return profile

    def save_profile(self, identity: OperatorIdentity, profile: OperatorProfile) -> None:
        identity.require_profile_match(profile.operator_id)

        path = self._profile_path(identity.operator_id)
        with _writer_guard(path,'PROFILE_WRITE_CONFLICT'):
            current=self.load_profile(identity) if path.exists() else None
            if getattr(current,'_custody_baseline',None)!=getattr(profile,'_custody_baseline',None):
                raise ValueError('PROFILE_WRITE_CONFLICT: explicit reload required')
            profile.touch()
            OperatorProfile.from_dict(profile.to_dict())
            self._write_json(path,profile.to_dict())
            profile._custody_baseline=digest(profile.to_dict())

        self.set_current_operator_id(identity.operator_id)

    def get_or_create_profile(
        self,
        operator_id: Optional[str] = None,
    ) -> tuple[OperatorIdentity, OperatorProfile]:
        resolved_operator_id = operator_id or self.get_current_operator_id()

        identity = OperatorIdentity.create(operator_id=resolved_operator_id)

        if self.profile_exists(identity.operator_id):
            profile = self.load_profile(identity)
        else:
            profile = self.create_profile(identity)

        self.set_current_operator_id(identity.operator_id)

        return identity, profile
