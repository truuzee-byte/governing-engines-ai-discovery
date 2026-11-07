from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from .config import BridgeConfig


def build_auth_dependency(config: BridgeConfig):
    expected = config.require_token()

    async def require_supervisor_token(authorization: str | None = Header(default=None)) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing supervisor token")
        supplied = authorization[7:].strip()
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=403, detail="invalid supervisor token")

    return require_supervisor_token
