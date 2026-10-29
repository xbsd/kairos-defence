"""``create_app`` (SPEC §16): the FastAPI app with its REST routes, the replay WebSocket and,
optionally, the built web app at ``/`` (``make demo``: one process, one origin, offline)."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from kairos_defense import __version__
from kairos_defense.api import (
    routes,
    routes_chat,
    routes_explain,
    routes_memory,
    routes_swarm,
    stream,
)

log = logging.getLogger(__name__)


def create_app(cfg=None, *, static_dir: Path | str | None = None,
               memory_path: Path | str | None = None, live_path: Path | str | None = None,
               reseed: bool = False,
               exports_path: Path | str | None = None) -> FastAPI:  # fmt: skip
    """The app. ``cfg=None`` builds a schema-only app (``--dump-openapi``): no lifespan, no
    services. Services are built on startup and closed on shutdown."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from kairos_defense.api.services import Services

        app.state.services = Services(cfg, memory_path=memory_path, live_path=live_path,
                                      reseed=reseed, exports_path=exports_path)  # fmt: skip
        log.info("API ready: %s", app.state.services.health())
        try:
            yield
        finally:
            app.state.services.close()

    app = FastAPI(title="Kairos Defense API", version=__version__,
                  description="Synthetic data only. REST (SPEC §16.4) and the replay stream "
                              "/ws/replay/{incident_id} (§16.3).",
                  lifespan=lifespan if cfg is not None else None)  # fmt: skip
    app.include_router(routes.router)
    app.include_router(routes_memory.router)
    app.include_router(routes_explain.router)
    app.include_router(routes_swarm.router)
    app.include_router(routes_chat.router)
    app.include_router(stream.router)
    if static_dir is not None:
        from kairos_defense.api.static import mount_web

        mount_web(app, static_dir)
    return app


def factory() -> FastAPI:
    """App factory for ``uvicorn --reload`` (``make dev``): options come from ``KD_*``."""
    from kairos_defense.config import load_config

    env = os.environ
    return create_app(load_config(env.get("KD_CONFIG", "config")),
                      static_dir=env.get("KD_STATIC") or None,
                      memory_path=env.get("KD_MEMORY") or None,
                      live_path=env.get("KD_LIVE_DB") or None,
                      exports_path=env.get("KD_EXPORTS") or None)  # fmt: skip
