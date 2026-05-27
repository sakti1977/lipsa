"""
Add data_source_type and purpose columns to search_jobs (for Hybrid + Guardrails direction)

Revision ID: 20250528_0002
Revises: 20250527_0001
Create Date: 2026-05-28

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "20250528_0002"
down_revision = "20250527_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "search_jobs",
        sa.Column("data_source_type", sa.String(), nullable=False, server_default="public_scrape"),
    )
    op.add_column(
        "search_jobs",
        sa.Column("purpose", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("search_jobs", "purpose")
    op.drop_column("search_jobs", "data_source_type")
