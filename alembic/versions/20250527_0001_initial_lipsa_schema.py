"""
Initial LIPSA schema (PR #2)

This migration creates the complete database schema as defined in the
approved design document (Storage Schema section + ER Diagram).

Tables:
- search_jobs
- job_runs
- posts (with mentions JSON, full denormalized author fields, raw_provider_data)
- authors (optional normalized lookup)
- audit_events (immutable consent + audit trail)
- media (normalized attachments)

Includes all indexes specified in the design and SQLite WAL-friendly setup
(the actual pragmas are applied in lipsa/storage/db.py on connect).

Revision ID: 20250527_0001
Revises: None
Create Date: 2026-05-27
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20250527_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # search_jobs
    op.create_table(
        "search_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("provider_preference", sa.String(), nullable=True),
        sa.Column("schedule_cron", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("disclaimer_version", sa.String(), nullable=False),
        sa.Column("consent_ack_token", sa.String(), nullable=True),
    )

    # job_runs
    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("job_id", sa.String(), sa.ForeignKey("search_jobs.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("posts_collected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_used", sa.String(), nullable=True),
        sa.Column("raw_metadata", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_job_runs_status", "job_runs", ["status"])

    # posts (exact columns from design + review feedback)
    op.create_table(
        "posts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("job_id", sa.String(), sa.ForeignKey("search_jobs.id"), nullable=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("job_runs.id"), nullable=True),
        sa.Column("post_urn", sa.String(), nullable=False, unique=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("author_name", sa.String(), nullable=False),
        sa.Column("author_headline", sa.String(), nullable=True),
        sa.Column("author_profile_url", sa.String(), nullable=False),
        sa.Column("author_company", sa.String(), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=False),
        sa.Column("reactions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("comments_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reposts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reaction_breakdown", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("media", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("hashtags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "mentions", sa.JSON(), nullable=False, server_default="[]"
        ),  # alignment fix from review
        sa.Column("is_repost", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("content_type", sa.String(), nullable=False, server_default="text"),
        sa.Column("raw_provider_data", sa.JSON(), nullable=False, server_default="{}"),
    )

    # Indexes exactly as specified in the design
    op.create_index("idx_posts_posted_at", "posts", ["posted_at"])
    op.create_index("idx_posts_job_id", "posts", ["job_id"])
    op.create_index("idx_posts_author_profile_url", "posts", ["author_profile_url"])
    op.create_index("idx_posts_job_posted", "posts", ["job_id", "posted_at"])

    # authors (optional normalized lookup)
    op.create_table(
        "authors",
        sa.Column("profile_url", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("headline", sa.String(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False, server_default="{}"),
    )

    # audit_events (immutable legal trail)
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), sa.ForeignKey("search_jobs.id"), nullable=True),
        sa.Column("query_hash", sa.String(), nullable=True),
        sa.Column("disclaimer_version", sa.String(), nullable=True),
        sa.Column("user_ack", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("idx_audit_events_job_timestamp", "audit_events", ["job_id", "timestamp"])
    op.create_index("idx_audit_events_type", "audit_events", ["event_type"])

    # media (normalized attachments)
    op.create_table(
        "media",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "post_id", sa.String(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False, server_default="image"),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("media")
    op.drop_index("idx_audit_events_type", table_name="audit_events")
    op.drop_index("idx_audit_events_job_timestamp", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("authors")
    op.drop_index("idx_posts_job_posted", table_name="posts")
    op.drop_index("idx_posts_author_profile_url", table_name="posts")
    op.drop_index("idx_posts_job_id", table_name="posts")
    op.drop_index("idx_posts_posted_at", table_name="posts")
    op.drop_table("posts")
    op.drop_index("ix_job_runs_status", table_name="job_runs")
    op.drop_table("job_runs")
    op.drop_table("search_jobs")
