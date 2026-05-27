"""
SQLAlchemy declarative models.

These are kept in close sync with the approved Storage Schema in the design document
(including the exact posts table columns, JSON fields, indexes, and audit_events structure).

The Pydantic models (lipsa.models) are the canonical interchange format.
These SQLAlchemy models are the persistence implementation.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class DataSourceType(StrEnum):
    """Type of data source. Mirrors the Pydantic version for DB storage."""
    PUBLIC_SCRAPE = "public_scrape"
    SALES_NAVIGATOR_EXPORT = "sales_navigator_export"
    LINKEDIN_DATA_EXPORT = "linkedin_data_export"
    COMPANY_OWNED_API = "company_owned_api"
    MANUAL_IMPORT = "manual_import"
    OTHER = "other"


class Base(DeclarativeBase):
    """Base class for all LIPSA SQLAlchemy models."""
    pass


class SearchJobModel(Base):
    __tablename__ = "search_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    provider_preference: Mapped[str | None] = mapped_column(String)
    schedule_cron: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Consent / audit linkage (critical for legal model)
    disclaimer_version: Mapped[str] = mapped_column(String, nullable=False)
    consent_ack_token: Mapped[str | None] = mapped_column(String)

    # Hybrid + Legal strengthening (Options 2 + 3)
    data_source_type: Mapped[str] = mapped_column(String, default="public_scrape", nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text)  # User-declared purpose / lawful basis

    # Relationships
    runs: Mapped[list[JobRunModel]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    posts: Mapped[list[PostModel]] = relationship(back_populates="job")


class JobRunModel(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("search_jobs.id"), nullable=False)

    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    posts_collected: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    provider_used: Mapped[str | None] = mapped_column(String)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    job: Mapped[SearchJobModel] = relationship(back_populates="runs")
    posts: Mapped[list[PostModel]] = relationship(back_populates="run")


class PostModel(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("search_jobs.id"))
    run_id: Mapped[str | None] = mapped_column(ForeignKey("job_runs.id"))

    post_urn: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Denormalized author snapshot (primary storage per design)
    author_name: Mapped[str] = mapped_column(String, nullable=False)
    author_headline: Mapped[str | None] = mapped_column(String)
    author_profile_url: Mapped[str] = mapped_column(String, nullable=False)
    author_company: Mapped[str | None] = mapped_column(String)

    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    reactions_count: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    reposts_count: Mapped[int] = mapped_column(Integer, default=0)

    reaction_breakdown: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    media: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)
    mentions: Mapped[list[str]] = mapped_column(JSON, default=list)  # aligned with Pydantic

    is_repost: Mapped[bool] = mapped_column(Boolean, default=False)
    content_type: Mapped[str] = mapped_column(String, default="text")

    raw_provider_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Relationships
    job: Mapped[SearchJobModel | None] = relationship(back_populates="posts")
    run: Mapped[JobRunModel | None] = relationship(back_populates="posts")

    # Indexes per design
    __table_args__ = (
        Index("idx_posts_posted_at", "posted_at"),
        Index("idx_posts_job_id", "job_id"),
        Index("idx_posts_author_profile_url", "author_profile_url"),
        Index("idx_posts_job_posted", "job_id", "posted_at"),
    )


class AuthorModel(Base):
    """
    Optional normalized author lookup table.
    Primary author data remains denormalized on posts (per design decision).
    """
    __tablename__ = "authors"

    profile_url: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    headline: Mapped[str | None] = mapped_column(String)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AuditEventModel(Base):
    """
    Immutable audit trail for legal/compliance defensibility.
    Mirrors and will eventually replace/augment the file-based ~/.lipsa/audit.log.
    """
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)

    job_id: Mapped[str | None] = mapped_column(ForeignKey("search_jobs.id"))
    query_hash: Mapped[str | None] = mapped_column(String)
    disclaimer_version: Mapped[str | None] = mapped_column(String)
    user_ack: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("idx_audit_events_job_timestamp", "job_id", "timestamp"),
    )


class MediaModel(Base):
    """Normalized media table (optional; many designs keep media JSON on posts)."""
    __tablename__ = "media"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)

    url: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, default="image")
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
