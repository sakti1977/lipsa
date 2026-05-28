"""
APScheduler integration for LIPSA.

Key design principles (from legal guardrails):
- Jobs are persistent (SQLAlchemyJobStore).
- No job runs without a valid consent snapshot captured at creation/edit time.
- If disclaimer_version or purpose changes, the job is paused until re-acknowledged.
- The scheduler can be started with `lipsa scheduler start`.
"""

from __future__ import annotations

import logging

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from lipsa.storage.db import get_database_url
from lipsa.storage.models import SearchJobModel

# Re-export for use in CLI (temporary until better structure)
__all__ = ["_run_scheduled_job"]  # for CLI resume hack during P5 development

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """Get or create the singleton APScheduler instance with SQLAlchemy persistence."""
    global _scheduler

    if _scheduler is not None:
        return _scheduler

    jobstores = {"default": SQLAlchemyJobStore(url=get_database_url())}

    executors = {"default": ThreadPoolExecutor(20)}

    job_defaults = {
        "coalesce": True,  # Combine missed runs
        "max_instances": 1,  # Only one instance of each job at a time
        "misfire_grace_time": 3600,  # Allow 1 hour late starts
    }

    _scheduler = BackgroundScheduler(
        jobstores=jobstores, executors=executors, job_defaults=job_defaults, timezone="UTC"
    )

    return _scheduler


def start_scheduler() -> None:
    """Start the background scheduler and load all eligible scheduled jobs."""
    scheduler = get_scheduler()

    if scheduler.running:
        logger.warning("Scheduler is already running.")
        return

    load_scheduled_jobs(scheduler)
    scheduler.start()
    logger.info("LIPSA scheduler started.")


def shutdown_scheduler(wait: bool = True) -> None:
    """Shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=wait)
        _scheduler = None
        logger.info("LIPSA scheduler shut down.")


def schedule_job(job_id: str, cron_expression: str, func: callable, **kwargs) -> None:
    """Add or replace a scheduled job in APScheduler."""
    scheduler = get_scheduler()
    scheduler.add_job(
        func, trigger="cron", id=job_id, replace_existing=True, args=[job_id], **kwargs
    )
    logger.info(f"Scheduled job {job_id} with cron: {cron_expression}")


def unschedule_job(job_id: str) -> None:
    """Remove a job from the scheduler."""
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Unscheduled job {job_id}")
    except Exception:
        pass


def load_scheduled_jobs(scheduler: BackgroundScheduler | None = None) -> None:
    """
    Load all active scheduled jobs from the database that have a valid consent snapshot.

    This is the core legal guardrail for P5:
    - Only jobs where consent_disclaimer_version matches the current DISCLAIMER_VERSION
      and a consent snapshot exists will be loaded.
    - Jobs with stale consent are skipped (user must update + re-ack them).
    """
    from lipsa.legal.disclaimer import DISCLAIMER_VERSION
    from lipsa.storage.db import get_session

    if scheduler is None:
        scheduler = get_scheduler()

    session = get_session()
    try:
        stmt = select(SearchJobModel).where(SearchJobModel.schedule_cron.isnot(None))
        scheduled_jobs = session.execute(stmt).scalars().all()

        loaded = 0
        skipped = 0

        for job in scheduled_jobs:
            # Strict consent snapshot validation (P5 requirement)
            has_valid_snapshot = (
                job.consent_disclaimer_version == DISCLAIMER_VERSION
                and job.consent_purpose is not None
                and job.consent_timestamp is not None
            )

            if has_valid_snapshot and job.schedule_cron:
                try:
                    scheduler.add_job(
                        _run_scheduled_job,
                        trigger="cron",
                        id=job.id,
                        replace_existing=True,
                        args=[job.id],
                        cron=job.schedule_cron,
                    )
                    loaded += 1
                    logger.info(f"Loaded scheduled job {job.id} with valid consent snapshot.")
                except Exception as e:
                    logger.error(f"Failed to load scheduled job {job.id}: {e}")
            else:
                skipped += 1
                logger.warning(
                    f"Skipped scheduled job {job.id} - consent snapshot is missing or stale "
                    f"(current version: {DISCLAIMER_VERSION}, job version: {job.consent_disclaimer_version}). "
                    f"User must update the job and re-acknowledge consent."
                )

        logger.info(
            f"Loaded {loaded} scheduled jobs. Skipped {skipped} due to invalid/stale consent."
        )

    finally:
        session.close()


def _run_scheduled_job(job_id: str) -> None:
    """
    Internal function executed by APScheduler for a recurring job.

    Performs last-moment consent validation before execution (defense in depth).
    """
    from lipsa.legal.disclaimer import DISCLAIMER_VERSION
    from lipsa.storage.db import get_session
    from lipsa.storage.repositories import create_job_run, finish_job_run

    logger.info(f"Executing scheduled job {job_id}")

    session = get_session()
    try:
        job = session.get(SearchJobModel, job_id)
        if not job:
            logger.error(f"Scheduled job {job_id} no longer exists.")
            return

        # Final consent check at execution time
        if job.consent_disclaimer_version != DISCLAIMER_VERSION or not job.consent_purpose:
            logger.error(
                f"Scheduled job {job_id} has stale consent. Skipping execution. "
                f"User must update the job and re-acknowledge."
            )
            # Create a failed run record for audit purposes
            run = create_job_run(session, job_id=job_id, provider_used="scheduled")
            finish_job_run(
                session,
                run.id,
                status="failed",
                error_message="Consent snapshot is stale. Job requires re-acknowledgment.",
            )
            session.commit()
            return

        run = create_job_run(session, job_id=job_id, provider_used="scheduled")

        # TODO: Replace placeholder with actual collection logic (importer or scraper)
        # based on job.data_source_type

        finish_job_run(
            session,
            run.id,
            status="success",
            posts_collected=0,  # placeholder until real execution is wired
        )
        session.commit()
        logger.info(f"Completed scheduled run for job {job_id}")

    except Exception as e:
        logger.exception(f"Scheduled job {job_id} failed: {e}")
        # Best effort to record failure
        try:
            run = create_job_run(session, job_id=job_id, provider_used="scheduled")
            finish_job_run(session, run.id, status="failed", error_message=str(e))
            session.commit()
        except Exception:
            pass
    finally:
        session.close()
