from __future__ import annotations

import uvicorn

from .api import create_app
from .config import BridgeConfig
from .service import SupervisorBridgeService


def main() -> None:
    config = BridgeConfig()
    service = SupervisorBridgeService(config)
    uvicorn.run(create_app(service), host=config.host, port=config.port)


if __name__ == "__main__":
    main()
