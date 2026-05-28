"""
Pydantic schemas for SearchJob and JobRun (the job management layer).

These represent the persistent search definitions and their execution history.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lipsa.models.post import Filters


class DataSourceType(StrEnum):
    """Type of data source for a collection job. Used for legal risk tiering."""

    PUBLIC_SCRAPE = "public_scrape"  # Via Apify/Bright Data etc. (highest risk)
    SALES_NAVIGATOR_EXPORT = "sales_navigator_export"
    LINKEDIN_DATA_EXPORT = "linkedin_data_export"
    COMPANY_OWNED_API = "company_owned_api"
    MANUAL_IMPORT = "manual_import"
    OTHER = "other"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    MISSED = "missed"
    CANCELLED = "cancelled"


class SearchJob(BaseModel):
    """A persistent search definition (one-off or recurring)."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: str
    name: str
    query: str
    filters: Filters
    data_source_type: DataSourceType = DataSourceType.PUBLIC_SCRAPE
    purpose: str | None = None  # User-declared purpose / lawful basis
    provider_preference: str | None = None  # "apify", "brightdata", etc.
    schedule_cron: str | None = None  # e.g. "0 9 * * MON"
    last_run_at: datetime | None = None
    created_at: datetime
    disclaimer_version: str
    consent_ack_token: str | None = None  # ties to audit_events

    # Consent snapshot (for recurring jobs - P5 legal requirement)
    consent_disclaimer_version: str | None = None
    consent_purpose: str | None = None
    consent_timestamp: datetime | None = None


class SearchJobCreate(BaseModel):
    name: str
    query: str
    filters: Filters
    data_source_type: DataSourceType = DataSourceType.PUBLIC_SCRAPE
    purpose: str | None = None
    provider_preference: str | None = None
    schedule_cron: str | None = None

    # Consent snapshot will be populated by the system at creation time for scheduled jobs
    consent_disclaimer_version: str | None = None
    consent_purpose: str | None = None
    consent_timestamp: datetime | None = None


class JobRun(BaseModel):
    """One execution of a SearchJob."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: str
    job_id: str
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None = None
    posts_collected: int = 0
    estimated_cost_usd: float | None = None
    error_message: str | None = None
    provider_used: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class JobRunCreate(BaseModel):
    job_id: str
    provider_used: str | None = None
