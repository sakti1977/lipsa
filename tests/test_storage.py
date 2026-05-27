"""
Tests for the PR #2 persistence layer (models, repositories, deduplication, migrations).
"""

from datetime import UTC, datetime

import pytest
from pydantic import HttpUrl

from lipsa.models.post import Filters, Post
from lipsa.storage.db import get_engine, get_session
from lipsa.storage.models import Base
from lipsa.storage.repositories import bulk_upsert_posts, create_search_job, upsert_post


@pytest.fixture(scope="function")
def db_session(tmp_path, monkeypatch):
    """Provide an isolated in-memory or temp-file database session for each test."""
    # Force a temp database for tests
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # crude but effective for get_database_path on Windows
    monkeypatch.setenv("HOME", str(tmp_path))

    # Recreate engine pointing at test DB
    from lipsa.storage import db as db_module
    db_module._engine = None
    db_module._SessionLocal = None

    engine = get_engine()
    Base.metadata.create_all(engine)  # quick bootstrap for tests (Alembic not needed here)

    session = get_session()
    yield session
    session.close()


def make_sample_post(urn: str = "urn:li:activity:123") -> Post:
    return Post(
        post_urn=urn,
        url=HttpUrl("https://www.linkedin.com/posts/example"),
        text="Great post about AI and the future of work.",
        author_name="Jane Doe",
        author_headline="AI Researcher @ ExampleCorp",
        author_profile_url=HttpUrl("https://www.linkedin.com/in/janedoe"),
        author_company="ExampleCorp",
        posted_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
        reactions_count=142,
        comments_count=23,
        hashtags=["ai", "futureofwork"],
        mentions=["urn:li:person:abc"],
    )


def test_urn_deduplication(db_session):
    """Core requirement: inserting the same post_urn twice should result in only one row."""
    post = make_sample_post()

    p1, created1 = upsert_post(db_session, post, job_id=None, run_id=None)
    db_session.commit()
    assert created1 is True

    p2, created2 = upsert_post(db_session, post, job_id=None, run_id=None)
    db_session.commit()
    assert created2 is False
    assert p1.id == p2.id

    # Only one row in DB
    from sqlalchemy import select

    from lipsa.storage.models import PostModel
    count = db_session.execute(select(PostModel)).scalars().all()
    assert len(count) == 1


def test_bulk_upsert_dedup(db_session):
    posts = [
        make_sample_post("urn:li:activity:1"),
        make_sample_post("urn:li:activity:1"),  # duplicate
        make_sample_post("urn:li:activity:2"),
    ]
    inserted, skipped = bulk_upsert_posts(db_session, posts)
    db_session.commit()
    assert inserted == 2
    assert skipped == 1


def test_create_search_job_and_run(db_session):
    job = create_search_job(
        db_session,
        name="AI Monitoring",
        query="#artificialintelligence",
        filters_json=Filters(max_results=200).model_dump(),
        disclaimer_version="2026-05-27",
        consent_ack_token="ack_123",
    )
    db_session.commit()

    assert job.id is not None
    assert job.query == "#artificialintelligence"

    from lipsa.storage.repositories import create_job_run, finish_job_run

    run = create_job_run(db_session, job_id=job.id, provider_used="apify")
    finish_job_run(db_session, run.id, status="success", posts_collected=87, estimated_cost_usd=0.42)
    db_session.commit()

    assert run.status == "success"
    assert run.posts_collected == 87
