"""
Scraper Backend abstraction (Protocol).

This is the core interface introduced in PR #3 per the approved design.

All backends (Apify, Bright Data, future self-managed) must implement this
so the rest of the application (Job Manager, CLI, normalizer) stays decoupled
from any specific provider.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from lipsa.models.post import Filters, Post


@runtime_checkable
class ScraperBackend(Protocol):
    """
    Protocol for all collection backends.

    The design calls for:
    - search_posts(query, filters) returning normalized Posts
    - The backend is responsible for its own raw data fetching + basic normalization
    - Higher layers (JobMgr) handle persistence, client-side filtering, legal gates, etc.
    """

    name: str
    """Human-readable name of the backend (e.g. 'apify', 'brightdata')."""

    def search_posts(self, query: str, filters: Filters) -> list[Post]:
        """
        Execute a search for the given query + filters and return
        a list of normalized Post objects.

        Implementations should:
        - Translate as many filters as possible to the provider's native format
        - Perform reasonable pagination / limits
        - Return only successfully normalized items (skip bad rows with logging)
        - Attach full raw_provider_data on each Post for fidelity
        """
        ...


class ScraperError(Exception):
    """Base exception for all scraper-related failures."""

    pass


class AuthenticationError(ScraperError):
    """Raised when API token is missing or invalid."""

    pass


class ProviderRateLimitError(ScraperError):
    """Raised when the provider rate-limits or quotas are exceeded."""

    pass
