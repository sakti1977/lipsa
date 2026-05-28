"""
Repository layer for LIPSA.

Provides clean CRUD operations and important business logic such as:
- URN-based deduplication when inserting posts
- Consent / audit linkage helpers
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from lipsa.models.post import Post as PostSchema
from lipsa.storage.models import (
    AuditEventModel,
    JobRunModel,
    PostModel,
    SearchJobModel,
)


def generate_id() -> str:
    """Short unique ID (sufficient for local single-user use)."""
    return uuid4().hex[:12]


# =============================================================================
# SearchJob
# =============================================================================
def create_search_job(
    session: Session,
    name: str,
    query: str,
    filters_json: dict[str, Any],
    disclaimer_version: str,
    data_source_type: str = "public_scrape",
    purpose: str | None = None,
    provider_preference: str | None = None,
    schedule_cron: str | None = None,
    consent_ack_token: str | None = None,
) -> SearchJobModel:
    now = datetime.utcnow()

    job = SearchJobModel(
        id=generate_id(),
        name=name,
        query=query,
        filters_json=filters_json,
        data_source_type=data_source_type,
        purpose=purpose,
        provider_preference=provider_preference,
        schedule_cron=schedule_cron,
        created_at=now,
        disclaimer_version=disclaimer_version,
        consent_ack_token=consent_ack_token,
    )

    # For scheduled/recurring jobs, capture a consent snapshot at creation time.
    # This is a core legal requirement (P5).
    if schedule_cron:
        job.consent_disclaimer_version = disclaimer_version
        job.consent_purpose = purpose
        job.consent_timestamp = now

    session.add(job)
    session.flush()
    return job


def get_search_job(session: Session, job_id: str) -> SearchJobModel | None:
    return session.get(SearchJobModel, job_id)


def update_search_job(
    session: Session,
    job_id: str,
    name: str | None = None,
    query: str | None = None,
    schedule_cron: str | None = None,
    purpose: str | None = None,
    provider_preference: str | None = None,
    consent_disclaimer_version: str | None = None,
    consent_purpose: str | None = None,
    consent_timestamp: datetime | None = None,
) -> SearchJobModel | None:
    """Update a job. Returns the updated job or None if not found.

    When schedule_cron or purpose is changed on a recurring job,
    the caller should also pass fresh consent snapshot values.
    """
    job = session.get(SearchJobModel, job_id)
    if not job:
        return None

    if name is not None:
        job.name = name
    if query is not None:
        job.query = query
    if schedule_cron is not None:
        job.schedule_cron = schedule_cron
    if purpose is not None:
        job.purpose = purpose
    if provider_preference is not None:
        job.provider_preference = provider_preference

    # Update consent snapshot if provided (happens after re-acknowledgment)
    if consent_disclaimer_version is not None:
        job.consent_disclaimer_version = consent_disclaimer_version
    if consent_purpose is not None:
        job.consent_purpose = consent_purpose
    if consent_timestamp is not None:
        job.consent_timestamp = consent_timestamp

    session.flush()
    return job


def delete_search_job(session: Session, job_id: str) -> bool:
    """Delete a job and its runs. Returns True if deleted."""
    job = session.get(SearchJobModel, job_id)
    if not job:
        return False

    # Delete associated runs first
    runs = session.execute(select(JobRunModel).where(JobRunModel.job_id == job_id)).scalars().all()
    for run in runs:
        session.delete(run)

    session.delete(job)
    session.flush()
    return True


def pause_job(session: Session, job_id: str) -> bool:
    """Pause a scheduled job (sets schedule_cron to None temporarily)."""
    job = session.get(SearchJobModel, job_id)
    if not job or not job.schedule_cron:
        return False

    # Store original cron in raw_metadata or a new field. For simplicity, we'll just remove it for now.
    # Better approach: add an `is_paused` field later.
    job.schedule_cron = None  # Simple pause for now
    session.flush()
    return True


def resume_job(session: Session, job_id: str, new_cron: str | None = None) -> bool:
    """Resume a paused job."""
    job = session.get(SearchJobModel, job_id)
    if not job:
        return False

    # In a real implementation we'd store the original cron.
    # For this step, user must provide the cron again when resuming.
    if new_cron:
        job.schedule_cron = new_cron
    else:
        return False  # Require cron for now

    session.flush()
    return True


def list_recent_jobs(session: Session, limit: int = 20) -> list[SearchJobModel]:
    stmt = select(SearchJobModel).order_by(SearchJobModel.created_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars())


def get_runs_for_job(session: Session, job_id: str) -> list[JobRunModel]:
    stmt = (
        select(JobRunModel)
        .where(JobRunModel.job_id == job_id)
        .order_by(JobRunModel.started_at.desc())
    )
    return list(session.execute(stmt).scalars())


# =============================================================================
# JobRun
# =============================================================================
def create_job_run(
    session: Session,
    job_id: str,
    provider_used: str | None = None,
) -> JobRunModel:
    run = JobRunModel(
        id=generate_id(),
        job_id=job_id,
        status="running",
        started_at=datetime.utcnow(),
        provider_used=provider_used,
    )
    session.add(run)
    session.flush()
    return run


def finish_job_run(
    session: Session,
    run_id: str,
    status: str,
    posts_collected: int = 0,
    estimated_cost_usd: float | None = None,
    error_message: str | None = None,
) -> JobRunModel | None:
    run = session.get(JobRunModel, run_id)
    if run:
        run.status = status
        run.finished_at = datetime.utcnow()
        run.posts_collected = posts_collected
        run.estimated_cost_usd = estimated_cost_usd
        run.error_message = error_message
        session.flush()
    return run


# =============================================================================
# Posts + Deduplication (core value of PR #2)
# =============================================================================
def upsert_post(
    session: Session,
    post: PostSchema,
    job_id: str | None = None,
    run_id: str | None = None,
) -> tuple[PostModel, bool]:
    """
    Insert a post or skip if the post_urn already exists.

    Returns (post_model, was_created).
    This implements the URN deduplication logic required by the design.
    """
    existing = session.execute(
        select(PostModel).where(PostModel.post_urn == post.post_urn)
    ).scalar_one_or_none()

    if existing:
        return existing, False

    pm = PostModel(
        id=generate_id(),
        job_id=job_id,
        run_id=run_id,
        post_urn=post.post_urn,
        url=str(post.url),
        text=post.text,
        author_name=post.author_name,
        author_headline=post.author_headline,
        author_profile_url=str(post.author_profile_url),
        author_company=post.author_company,
        posted_at=post.posted_at,
        reactions_count=post.reactions_count,
        comments_count=post.comments_count,
        reposts_count=post.reposts_count,
        reaction_breakdown=post.reaction_breakdown,
        media=[m.model_dump() for m in post.media],
        hashtags=post.hashtags,
        mentions=post.mentions,
        is_repost=post.is_repost,
        content_type=post.content_type,
        raw_provider_data=post.raw_provider_data,
    )
    session.add(pm)
    session.flush()
    return pm, True


def bulk_upsert_posts(
    session: Session,
    posts: Iterable[PostSchema],
    job_id: str | None = None,
    run_id: str | None = None,
) -> tuple[int, int]:
    """
    Bulk insert with deduplication.

    Returns (inserted_count, skipped_count).
    """
    inserted = 0
    skipped = 0
    for p in posts:
        _, created = upsert_post(session, p, job_id, run_id)
        if created:
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped


# =============================================================================
# Audit Events (DB side - complements the file log from PR #1)
# =============================================================================
def record_audit_event(
    session: Session,
    event_type: str,
    disclaimer_version: str | None = None,
    job_id: str | None = None,
    user_ack: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEventModel:
    evt = AuditEventModel(
        id=generate_id(),
        timestamp=datetime.utcnow(),
        event_type=event_type,
        job_id=job_id,
        disclaimer_version=disclaimer_version,
        user_ack=user_ack,
        details=details or {},
    )
    session.add(evt)
    session.flush()
    return evt


def get_recent_audit_events(session: Session, limit: int = 100) -> list[AuditEventModel]:
    return list(
        session.execute(
            select(AuditEventModel).order_by(AuditEventModel.timestamp.desc()).limit(limit)
        ).scalars()
    )


def get_audit_events_for_job(
    session: Session, job_id: str, limit: int = 500
) -> list[AuditEventModel]:
    """Get audit events related to a specific job (for compliance exports)."""
    stmt = (
        select(AuditEventModel)
        .where(AuditEventModel.job_id == job_id)
        .order_by(AuditEventModel.timestamp.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars())
