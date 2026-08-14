"""Log config and utils for the worker instance."""

from __future__ import annotations

import os
from functools import cache
from typing import TYPE_CHECKING, Any, cast

import structlog
from saq import CronJob, Queue, Status
from saq.utils import seconds

from app.lib.settings import get_settings

if TYPE_CHECKING:
    from saq import Job
    from saq.types import Context

LOGGED_JOB_FIELDS = [
    "function",
    "kwargs",
    "key",
    "scheduled",
    "attempts",
    "completed",
    "queued",
    "started",
    "result",
    "error",
]

logger = structlog.get_logger()


@cache
def saq_worker_settings() -> dict[str, Any]:
    """Return the SAQ worker settings dict used by the standalone worker process."""
    from app.domain.accounts import jobs as account_jobs
    from app.domain.carbon import jobs as carbon_jobs
    from app.domain.iot_ingestion import infrastructure as iot_infrastructure
    from app.domain.iot_ingestion import jobs as iot_jobs
    from app.domain.microgrid import jobs as microgrid_jobs
    from app.domain.system import jobs as system_jobs

    queue_name = os.getenv("SAQ_WORKER_QUEUE", "background-tasks")
    queue_configs = {item.name: item for item in get_settings().saq.get_config().queue_configs}
    settings = queue_configs.get(queue_name)
    if settings is None:
        msg = f"Unknown SAQ_WORKER_QUEUE: {queue_name}"
        raise ValueError(msg)
    is_mqtt_ingest = queue_name == "mqtt-ingest"
    functions = (
        [
            ("iot.ingest_mqtt_message", iot_jobs.ingest_mqtt_message),
            ("iot.retry_pending_mqtt_messages", iot_jobs.retry_pending_mqtt_messages),
        ]
        if is_mqtt_ingest
        else [
            system_jobs.cleanup_auth_tokens,
            account_jobs.refresh_oauth_tokens,
            carbon_jobs.sync_yunji_status,
            carbon_jobs.pull_yunji_data,
            carbon_jobs.sync_hw_status,
            carbon_jobs.pull_hw_data,
            carbon_jobs.execute_day_alarm_scan,
            carbon_jobs.execute_video_alarm_scan,
            microgrid_jobs.run_microgrid_forecast_cycle,
            microgrid_jobs.run_microgrid_optimization_cycle,
            microgrid_jobs.refresh_microgrid_load_models,
            microgrid_jobs.project_microgrid_meter_history,
        ]
    )
    return {
        "queue": Queue.from_url(settings.dsn, name=settings.name),
        "functions": functions,
        "concurrency": settings.concurrency,
        "cron_jobs": [
            CronJob(iot_jobs.retry_pending_mqtt_messages, "*/1 * * * *", timeout=300),
        ]
        if is_mqtt_ingest
        else [
            CronJob(system_jobs.cleanup_auth_tokens, "0 * * * *", timeout=600, ttl=1800),
            CronJob(account_jobs.refresh_oauth_tokens, "*/15 * * * *", timeout=600, ttl=1800),
            CronJob(carbon_jobs.sync_yunji_status, "0 * * * *", timeout=300),
            CronJob(carbon_jobs.sync_hw_status, "0 * * * *", timeout=300),
            CronJob(carbon_jobs.pull_yunji_data, "*/15 * * * *", timeout=600),
            CronJob(carbon_jobs.pull_hw_data, "0 1 * * *", timeout=1200),
            CronJob(carbon_jobs.execute_day_alarm_scan, "0 2 * * *", timeout=600),
            CronJob(carbon_jobs.execute_video_alarm_scan, "0 9-18 * * *", timeout=300),
            CronJob(microgrid_jobs.run_microgrid_forecast_cycle, "*/15 * * * *", timeout=600),
            CronJob(microgrid_jobs.run_microgrid_optimization_cycle, "2-59/15 * * * *", timeout=300),
            CronJob(microgrid_jobs.refresh_microgrid_load_models, "30 2 * * *", timeout=900),
            CronJob(microgrid_jobs.project_microgrid_meter_history, "7 * * * *", timeout=900),
        ],
        "startup": [on_startup, iot_infrastructure.on_mqtt_ingest_startup] if is_mqtt_ingest else [on_startup],
        "shutdown": [iot_infrastructure.on_mqtt_ingest_shutdown, on_shutdown] if is_mqtt_ingest else [on_shutdown],
        "before_process": [before_process],
        "after_process": [after_process],
        "metadata": {"app": get_settings().app.NAME},
    }


async def on_shutdown(ctx: Context) -> None:
    """Shutdown events for each worker."""
    worker = cast("Any", ctx["worker"])
    await logger.ainfo("Stopping background workers for queue", queue=worker.queue.name)


async def on_startup(ctx: Context) -> None:
    """Startup events for each worker."""
    worker = cast("Any", ctx["worker"])
    await logger.ainfo("🚀 Launching background workers for queue", queue=worker.queue.name)


async def before_process(ctx: Context) -> None:
    """Clear the structlog contextvars for this task."""
    structlog.contextvars.clear_contextvars()
    ctx_dict = cast("dict[str, Any]", ctx)
    job = cast("Job | None", ctx_dict.get("job"))
    if job:
        await logger.ainfo(f"starting job {job.function} with id {job.id}", task=job.function)


async def after_process(ctx: Context) -> None:
    """Parse log context and log it along with the contextvars context."""
    ctx_dict = cast("dict[str, Any]", ctx)
    job = cast("Job | None", ctx_dict.get("job"))
    if job:
        log_ctx = {k: getattr(job, k) for k in LOGGED_JOB_FIELDS}
        log_ctx["pickup_time_ms"] = job.started - job.queued
        log_ctx["total_runtime_ms"] = job.completed - job.started
        log_ctx["total_time_ms"] = job.completed - job.queued
        total_runtime_ms = seconds(log_ctx["total_runtime_ms"])
        if job.status == Status.FAILED:
            msg = f"job {job.function} with id '{job.id}' failed after {total_runtime_ms} seconds."
            await logger.aerror(msg, **log_ctx)
        elif job.status == Status.COMPLETE:
            msg = f"job {job.function} with id '{job.id}' completed after {total_runtime_ms} seconds."
            await logger.ainfo(msg, **log_ctx)
        elif job.status == Status.ABORTED:
            msg = f"job {job.function} with id '{job.id}' was aborted after {total_runtime_ms} seconds"
            await logger.awarning(msg, **log_ctx)
        else:
            msg = f"job {job.function} with id '{job.id}' {job.status} after {total_runtime_ms} seconds."
            await logger.ainfo(msg, **log_ctx)
    structlog.contextvars.clear_contextvars()
