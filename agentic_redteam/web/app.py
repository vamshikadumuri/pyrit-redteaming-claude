"""FastAPI web application (spec §13/§16). Container-only module — requires
fastapi, starlette, uvicorn in the image. Never imported by laptop tests."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from agentic_redteam.catalog.loader import load_catalog
from agentic_redteam.store import Store
from agentic_redteam.web import live
from agentic_redteam.web.manager import RunManager

_log = logging.getLogger(__name__)

_STATIC = Path(__file__).resolve().parent / "static"


def create_app(
    *,
    store_path: str = ":memory:",
    exec_factory=None,
    llm_factory=None,
) -> FastAPI:
    from contextlib import asynccontextmanager

    import agentic_redteam.web.deps as deps

    catalog = load_catalog()
    store = Store(store_path)

    @asynccontextmanager
    async def _lifespan(application: FastAPI):
        await store._open()
        try:
            from pyrit.setup import IN_MEMORY, initialize_pyrit_async

            await initialize_pyrit_async(memory_db_type=IN_MEMORY)
        except ImportError:
            pass  # PyRIT not installed (laptop / test environment)
        _log.info("App startup complete (store=%s)", store_path)
        try:
            yield
        finally:
            _log.info("App shutdown")
            await store.close()

    app = FastAPI(lifespan=_lifespan)
    if exec_factory is None:
        exec_factory = live.real_executor_factory
    if llm_factory is None:
        llm_factory = live.real_llm_factory
    manager = RunManager(
        catalog,
        store,
        executor_factory=exec_factory,
        llm_factory=llm_factory,
    )

    # Wire up dependency singletons
    deps._store = store
    deps._catalog = catalog
    deps._manager = manager

    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    from agentic_redteam.web.routes import runs, wizard

    app.include_router(wizard.router)
    app.include_router(runs.router)

    return app
