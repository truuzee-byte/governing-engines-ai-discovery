from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Protocol
from abc import ABC, abstractmethod

from builder.core.command_runner import run_approved_commands
from builder.core.file_writer import write_approved_files
from builder.core.workspace_manager import create_workspace


class KernelClient(Protocol):
    def create_workspace(self, required_directories: list[str]) -> list[str]: ...
    def write_files(self, approved_files: dict[str, str], required_files: list[str]) -> list[str]: ...
    def run_commands(self, commands: list[list[str]], approved_commands: list[list[str]]) -> list[dict]: ...


class OperationBoundKernelClient(ABC):
    """Trusted integration port; not a Kernel, credential or transport implementation.

    A concrete deployment adapter must authenticate the external Kernel, bind the
    exact approved operations, transfer admitted artifacts and return verified
    execution/retirement evidence. No implementation or host fallback is supplied.
    """
    @abstractmethod
    def bind(self, artifact_root, operations, snapshot_hash): ...
    @abstractmethod
    def create_workspace(self, required_directories): ...
    @abstractmethod
    def write_files(self, approved_files, required_files): ...
    @abstractmethod
    def run_commands(self, commands, approved_commands): ...


@dataclass
class BootstrapKernelClient:
    """Temporary pre-Kernel executor.

    This exists only so existing MODE/Builder can build the Kernel itself under
    external supervision. It reuses the existing bounded Builder primitives.
    Once the Trusted Execution Kernel is operational, replace this client with
    the real remote/local Kernel client and disable bootstrap execution.
    """

    artifact_root: str
    operations: dict[str, str] | None = None

    def create_workspace(self, required_directories: list[str]) -> list[str]:
        return create_workspace(self.artifact_root, required_directories)

    def write_files(self, approved_files: dict[str, str], required_files: list[str]) -> list[str]:
        return write_approved_files(self.artifact_root, approved_files, required_files, operations=self.operations)

    def run_commands(self, commands: list[list[str]], approved_commands: list[list[str]]) -> list[dict]:
        return run_approved_commands(commands, approved_commands, self.artifact_root)


class HttpKernelClient:
    """Interface placeholder for the real Trusted Execution Kernel.

    Deliberately fail-closed until the Kernel API exists. Do not silently fall
    back to direct host execution after the Kernel is declared operational.
    """

    def __init__(self, base_url: str, token: str, task_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.task_id = task_id

    def _not_ready(self) -> None:
        raise RuntimeError("Trusted Execution Kernel HTTP client not connected")

    def create_workspace(self, required_directories: list[str]) -> list[str]:
        self._not_ready()
        return []

    def write_files(self, approved_files: dict[str, str], required_files: list[str]) -> list[str]:
        self._not_ready()
        return []

    def run_commands(self, commands: list[list[str]], approved_commands: list[list[str]]) -> list[dict]:
        self._not_ready()
        return []
