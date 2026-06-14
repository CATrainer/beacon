"""Job enqueue helper. Falls back to inline execution if Redis is unreachable."""

from __future__ import annotations

import logging

from app.config import settings

log = logging.getLogger(__name__)


async def enqueue(func_name: str, *args) -> bool:
    """Enqueue an arq job. Returns False if Redis is unavailable so the caller can
    run it inline (FastAPI BackgroundTasks)."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await pool.enqueue_job(func_name, *args)
        finally:
            await pool.close()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("arq enqueue of %s failed (%s); falling back to inline", func_name, exc)
        return False
