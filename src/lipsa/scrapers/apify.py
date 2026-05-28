"""
Apify backend implementation for PR #3.

Uses the official `apify-client` to run popular no-cookie LinkedIn Post Search actors
and normalizes results into the canonical `Post` model.

Recommended actors (as of design time):
- harvestapi/linkedin-post-search (excellent ratings, good no-cookie support)
- supreme_coder/linkedin-post

This backend performs:
- Basic native filter translation (especially dates)
- Actor execution + dataset retrieval
- Normalization + attachment of raw_provider_data
- Client-side engagement filtering (min_reactions etc.)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from apify_client import ApifyClient

from lipsa.config import require_apify_token
from lipsa.models.post import Filters, MediaItem, Post
from lipsa.scrapers.base import AuthenticationError, ScraperBackend, ScraperError

logger = logging.getLogger(__name__)


# Popular no-cookie actors (can be made configurable later)
DEFAULT_ACTOR_ID = "harvestapi/linkedin-post-search"


class ApifyBackend(ScraperBackend):
    name = "apify"

    def __init__(self, actor_id: str | None = None, token: str | None = None):
        self.actor_id = actor_id or DEFAULT_ACTOR_ID
        self._token = token  # allow injection for testing

    @property
    def token(self) -> str:
        if self._token:
            return self._token
        return require_apify_token()

    def search_posts(self, query: str, filters: Filters) -> list[Post]:
        client = ApifyClient(self.token)

        run_input = self._build_actor_input(query, filters)

        logger.info(
            f"Starting Apify actor {self.actor_id} with input keys: {list(run_input.keys())}"
        )

        try:
            run = client.actor(self.actor_id).call(run_input=run_input)
        except Exception as exc:
            if "authentication" in str(exc).lower() or "token" in str(exc).lower():
                raise AuthenticationError("Invalid or missing Apify API token") from exc
            raise ScraperError(f"Apify actor run failed: {exc}") from exc

        # Fetch the dataset
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            raise ScraperError("Apify run completed but no dataset was produced")

        items = list(client.dataset(dataset_id).iterate_items())

        logger.info(f"Apify returned {len(items)} raw items")

        normalized: list[Post] = []
        for raw in items:
            try:
                post = self._normalize(raw)
                normalized.append(post)
            except Exception as e:
                logger.warning(f"Failed to normalize one Apify item: {e}")
                continue

        # Client-side filtering for engagement (design requirement)
        filtered = self._apply_client_side_filters(normalized, filters)

        # Respect max_results
        return filtered[: filters.max_results]

    def _build_actor_input(self, query: str, filters: Filters) -> dict[str, Any]:
        """
        Translate our Filters into the actor's expected input format.

        This is intentionally conservative for PR #3.
        We focus on the most reliable fields that most LinkedIn post search actors support.
        """
        input_data: dict[str, Any] = {
            "searchQuery": query,
            "maxResults": min(filters.max_results * 2, 2000),  # conservative over-fetch
        }

        # Date handling (very common pattern in Apify LinkedIn actors)
        date_filters: dict[str, Any] = {}
        if filters.date_from:
            date_filters["dateFrom"] = filters.date_from.strftime("%Y-%m-%d")
        if filters.date_to:
            date_filters["dateTo"] = filters.date_to.strftime("%Y-%m-%d")

        if date_filters:
            input_data["datePosted"] = date_filters

        # Sort order
        if filters.sort in ("latest", "top", "relevance"):
            input_data["sort"] = filters.sort

        # Basic keyword / hashtag is already in the main query

        return input_data

    def _normalize(self, raw: dict[str, Any]) -> Post:
        """Convert a raw Apify item into our canonical Post model."""
        # These field names are common across several popular LinkedIn post actors.
        # Real actors vary, so we use defensive .get() everywhere.
        post_urn = raw.get("urn") or raw.get("postUrn") or raw.get("id") or ""
        url = raw.get("url") or raw.get("postUrl") or ""

        text = raw.get("text") or raw.get("content") or ""

        author = raw.get("author") or {}
        author_name = author.get("name") or raw.get("authorName") or "Unknown"
        author_headline = author.get("headline") or raw.get("authorHeadline")
        author_profile_url = (
            author.get("profileUrl")
            or author.get("url")
            or raw.get("authorProfileUrl")
            or "https://www.linkedin.com"
        )

        posted_at_raw = raw.get("postedAt") or raw.get("date") or raw.get("timestamp")
        posted_at = self._parse_date(posted_at_raw)

        reactions = raw.get("reactionsCount") or raw.get("numLikes") or raw.get("likes") or 0
        comments = raw.get("commentsCount") or raw.get("numComments") or 0
        reposts = raw.get("repostsCount") or raw.get("numReposts") or 0

        media_list = self._extract_media(raw)

        hashtags = raw.get("hashtags") or []
        if isinstance(hashtags, str):
            hashtags = [h.strip() for h in hashtags.split(",") if h.strip()]

        mentions = raw.get("mentions") or []

        is_repost = bool(raw.get("isRepost") or raw.get("isReposted"))

        content_type = raw.get("contentType") or "text"

        return Post(
            post_urn=str(post_urn),
            url=url,
            text=str(text)[:10000],  # safety truncate
            author_name=str(author_name),
            author_headline=str(author_headline) if author_headline else None,
            author_profile_url=author_profile_url,
            author_company=raw.get("authorCompany"),
            posted_at=posted_at,
            reactions_count=int(reactions),
            comments_count=int(comments),
            reposts_count=int(reposts),
            reaction_breakdown=raw.get("reactionBreakdown") or {},
            media=media_list,
            hashtags=hashtags,
            mentions=mentions,
            is_repost=is_repost,
            content_type=str(content_type),
            raw_provider_data=raw,  # full fidelity
        )

    def _extract_media(self, raw: dict[str, Any]) -> list[MediaItem]:
        media_raw = raw.get("media") or raw.get("images") or []
        result: list[MediaItem] = []

        for m in media_raw:
            if isinstance(m, dict):
                url = m.get("url") or m.get("src")
                if url:
                    result.append(
                        MediaItem(
                            url=url,
                            type=m.get("type", "image"),
                            width=m.get("width"),
                            height=m.get("height"),
                        )
                    )
            elif isinstance(m, str):
                result.append(MediaItem(url=m))

        return result

    def _parse_date(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(value[:19], fmt)
                except ValueError:
                    continue
        # Fallback
        return datetime.now()

    def _apply_client_side_filters(self, posts: list[Post], filters: Filters) -> list[Post]:
        """Apply engagement filters that the provider may not have supported natively."""
        result = posts

        if filters.min_reactions is not None:
            result = [p for p in result if p.reactions_count >= filters.min_reactions]

        if filters.min_comments is not None:
            result = [p for p in result if p.comments_count >= filters.min_comments]

        return result
