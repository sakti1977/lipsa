"""
Pydantic schemas for Post-related entities (the canonical data model).

These are the "public" / interchange models used by the normalizer,
exporters, and future scraper backends. They are independent of the
database layer (SQLAlchemy models live in storage/models.py).

Aligned with the Storage Schema and ERD from the approved design.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class MediaItem(BaseModel):
    """Represents one media attachment (image, video, document, etc.)."""
    url: HttpUrl
    type: str = "image"  # image | video | pdf | article | ...
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None


class AuthorSnapshot(BaseModel):
    """Denormalized author information captured at collection time."""
    name: str
    headline: str | None = None
    profile_url: HttpUrl
    company: str | None = None


class Post(BaseModel):
    """
    Canonical representation of a LinkedIn post.

    This is the primary data contract. All scrapers must normalize into this.
    The DB layer stores most fields denormalized + raw_provider_data for fidelity.
    """
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    post_urn: str = Field(..., description="LinkedIn URN, e.g. urn:li:activity:1234567890")
    url: HttpUrl
    text: str
    author_name: str
    author_headline: str | None = None
    author_profile_url: HttpUrl
    author_company: str | None = None
    posted_at: datetime

    reactions_count: int = 0
    comments_count: int = 0
    reposts_count: int = 0
    reaction_breakdown: dict[str, int] = Field(default_factory=dict)

    media: list[MediaItem] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)  # e.g. profile URNs or @handles

    is_repost: bool = False
    content_type: str = "text"  # text | image | video | article | poll | carousel | ...

    # Full fidelity from the provider (for debugging, re-processing, future fields)
    raw_provider_data: dict[str, Any] = Field(default_factory=dict)


class PostCreate(Post):
    """Used when inserting a new post (no DB id yet)."""
    pass


class Filters(BaseModel):
    """
    Search filters that can be applied client-side or (partially) pushed to providers.
    """
    model_config = ConfigDict(extra="forbid")

    date_from: datetime | None = None
    date_to: datetime | None = None
    min_reactions: int | None = Field(None, ge=0)
    min_comments: int | None = Field(None, ge=0)
    author_types: list[str] = Field(default_factory=list)  # e.g. ["person", "company"]
    content_types: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    sort: str = "relevance"  # relevance | latest | top
    max_results: int = Field(500, ge=1, le=5000)
