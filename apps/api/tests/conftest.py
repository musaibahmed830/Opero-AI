import pytest_asyncio

from app.core.database import engine
from app.core.redis_client import get_redis_client


@pytest_asyncio.fixture(autouse=True)
async def _dispose_shared_clients_after_test():
    """Each test gets its own asyncio event loop (pytest-asyncio's function-scoped
    default), but the app's DB engine (app/core/database.py) and Redis client
    (app/core/redis_client.py) are module-level singletons whose pooled
    connections are bound to whichever loop first created them. Without
    disposing them, a later test's loop tries to reuse a connection tied to a
    now-closed loop and raises "Future attached to a different loop" / "Event
    loop is closed". Disposing after every test forces the next test to lazily
    open fresh connections under its own loop.
    """
    yield
    await engine.dispose()
    get_redis_client.cache_clear()
