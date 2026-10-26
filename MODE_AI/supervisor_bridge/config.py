from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BridgeConfig:
    host: str = os.getenv("MODE_SUPERVISOR_HOST", "127.0.0.1")
    port: int = int(os.getenv("MODE_SUPERVISOR_PORT", "8765"))
    db_path: str = os.getenv(
        "MODE_SUPERVISOR_DB",
        str(Path("runtime") / "supervisor_bridge.db"),
    )
    supervisor_token: str = os.getenv("MODE_SUPERVISOR_TOKEN", "")

    def require_token(self) -> str:
        token = self.supervisor_token.strip()
        if not token:
            raise RuntimeError(
                "MODE_SUPERVISOR_TOKEN is required before starting the bridge API"
            )
        return token
