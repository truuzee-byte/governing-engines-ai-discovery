from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class FileProposal:
    path: str
    operation: str
    content: str
    reason: str = ""
    spec_requirement: str = ""

    def __post_init__(self) -> None:
        if self.operation not in {"CREATE", "MODIFY"}:
            raise ValueError("operation must be CREATE or MODIFY")
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must be non-empty")
        if not isinstance(self.content, str):
            raise TypeError("content must be a string")


@dataclass(frozen=True)
class CommandProposal:
    argv: List[str]
    purpose: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.argv, list) or not self.argv:
            raise ValueError("argv must be a non-empty list")
        if any(not isinstance(part, str) or not part.strip() for part in self.argv):
            raise ValueError("argv must contain non-empty strings")


@dataclass(frozen=True)
class ConstructionProposal:
    files: List[FileProposal] = field(default_factory=list)
    commands: List[CommandProposal] = field(default_factory=list)
    unresolved_conditions: List[str] = field(default_factory=list)
    boundary_state: Optional[str] = None

    def approved_file_map(self) -> Dict[str, str]:
        return {item.path: item.content for item in self.files}
