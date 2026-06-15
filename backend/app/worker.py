"""arq worker — runs long jobs off the request path (§1).

Sync job bodies run in a thread so arq's event loop stays responsive. Start with:
    arq app.worker.WorkerSettings
(the compose `worker` service does this).
"""

from __future__ import annotations

import asyncio
import logging

from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.services.geo import execute_geo_job
from app.services.research import execute_research_job
from app.services.scoring import execute_score_job
from app.services.sending import execute_send_job
from app.services.sourcing import execute_source_job, run_scheduled_sourcing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def run_source_job(ctx: dict, job_id: int) -> None:
    await asyncio.to_thread(execute_source_job, job_id)


async def run_score_job(ctx: dict, job_id: int) -> None:
    await asyncio.to_thread(execute_score_job, job_id)


async def run_research_job(ctx: dict, job_id: int) -> None:
    await asyncio.to_thread(execute_research_job, job_id)


async def run_geo_job(ctx: dict, job_id: int) -> None:
    await asyncio.to_thread(execute_geo_job, job_id)


async def run_send_job(ctx: dict, job_id: int) -> None:
    await asyncio.to_thread(execute_send_job, job_id)


async def scheduled_sourcing_cron(ctx: dict) -> None:
    """Nightly incremental sourcing for active lanes (no-op unless enabled)."""
    await asyncio.to_thread(run_scheduled_sourcing)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [
        run_source_job, run_score_job, run_research_job, run_geo_job, run_send_job,
    ]
    # Fires daily; the job itself checks the (operator-toggleable) enabled flag.
    cron_jobs = [cron(scheduled_sourcing_cron, hour=settings.scheduled_sourcing_hour, minute=0)]
    max_jobs = 4
    job_timeout = 60 * 30  # 30 min ceiling for a job
