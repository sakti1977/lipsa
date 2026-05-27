"""Scraper backends for LIPSA."""

from lipsa.scrapers.apify import ApifyBackend
from lipsa.scrapers.base import ScraperBackend, ScraperError

__all__ = ["ScraperBackend", "ScraperError", "ApifyBackend", "get_backend"]


def get_backend(name: str = "apify") -> ScraperBackend:
    """Simple factory for PR #3. Can be expanded when Bright Data and others are added."""
    if name.lower() in ("apify", "default"):
        return ApifyBackend()
    raise ValueError(f"Unknown backend: {name}. Currently only 'apify' is supported in PR #3.")
