"""
Unit tests for PR #3 scraper layer (using mocks, no real API calls).
"""

from unittest.mock import MagicMock, patch

import pytest

from lipsa.models.post import Filters, Post
from lipsa.scrapers.apify import ApifyBackend


def make_fake_apify_item(urn: str = "urn:li:activity:999") -> dict:
    return {
        "urn": urn,
        "url": "https://www.linkedin.com/posts/test",
        "text": "This is a test post about AI.",
        "author": {
            "name": "Test User",
            "headline": "Engineer at TestCo",
            "profileUrl": "https://www.linkedin.com/in/testuser",
        },
        "postedAt": "2026-05-20",
        "reactionsCount": 87,
        "commentsCount": 12,
        "hashtags": ["ai", "testing"],
    }


def test_apify_backend_normalizes_correctly():
    backend = ApifyBackend(token="fake-token-for-test")

    raw = make_fake_apify_item()
    post = backend._normalize(raw)

    assert isinstance(post, Post)
    assert post.post_urn == "urn:li:activity:999"
    assert post.author_name == "Test User"
    assert post.reactions_count == 87
    assert "ai" in post.hashtags
    assert post.raw_provider_data == raw  # fidelity


@patch("lipsa.scrapers.apify.ApifyClient")
def test_apify_search_uses_actor_and_normalizes(mock_client_class):
    fake_items = [make_fake_apify_item(f"urn:li:activity:{i}") for i in range(5)]

    # Mock the Apify client chain
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_actor = MagicMock()
    mock_client.actor.return_value = mock_actor
    mock_actor.call.return_value = {"defaultDatasetId": "ds123"}

    mock_dataset = MagicMock()
    mock_client.dataset.return_value = mock_dataset
    mock_dataset.iterate_items.return_value = fake_items

    backend = ApifyBackend(token="test-token")
    filters = Filters(max_results=10)

    posts = backend.search_posts("#test", filters)

    assert len(posts) == 5
    assert all(isinstance(p, Post) for p in posts)
    mock_client.actor.assert_called_once()


def test_apify_backend_raises_on_missing_token():
    backend = ApifyBackend(token=None)  # force lookup

    with patch("lipsa.scrapers.apify.require_apify_token", side_effect=RuntimeError("no token")):
        with pytest.raises(RuntimeError):
            backend.search_posts("query", Filters())
