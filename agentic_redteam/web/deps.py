"""FastAPI dependency providers (spec §3b).

Module-level singletons are set by create_app() before the app starts serving.
Route handlers use Annotated[..., Depends(...)] to request them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentic_redteam.catalog.loader import Catalog
    from agentic_redteam.store import Store
    from agentic_redteam.web.manager import RunManager

# Set by create_app() before the app starts serving
_store: Store | None = None
_catalog: Catalog | None = None
_manager: RunManager | None = None


def get_store() -> Store:
    assert _store is not None, "Store not initialised — was create_app() called?"
    return _store


def get_catalog() -> Catalog:
    assert _catalog is not None, "Catalog not initialised — was create_app() called?"
    return _catalog


def get_manager() -> RunManager:
    assert _manager is not None, "RunManager not initialised — was create_app() called?"
    return _manager
