"""
LIPSA - LinkedIn Post Search & Collection Application

Local-first tool for searching and collecting public LinkedIn posts
by keyword or hashtag, with strong legal, ethical, and audit guardrails.

WARNING: Automated access to LinkedIn almost certainly violates their
User Agreement. See `lipsa legal show` and the README for full risks.
"""

__version__ = "0.1.0"

from lipsa.exporters import (
    CSVExporter,
    ExcelExporter,
    JSONExporter,
    ParquetExporter,
    export_posts,
)
from lipsa.importers import SalesNavigatorCSVImporter
from lipsa.legal.disclaimer import (
    DISCLAIMER_VERSION,
    audit_log_event,
    get_disclaimer_text,
    log_consent_acknowledgment,
    require_acknowledgment,
)
from lipsa.models.job import DataSourceType
from lipsa.storage import get_db_info, run_migrations

__all__ = [
    "__version__",
    "DISCLAIMER_VERSION",
    "get_disclaimer_text",
    "require_acknowledgment",
    "log_consent_acknowledgment",
    "audit_log_event",
    "get_db_info",
    "run_migrations",
    "DataSourceType",
    "SalesNavigatorCSVImporter",
    "CSVExporter",
    "ExcelExporter",
    "JSONExporter",
    "ParquetExporter",
    "export_posts",
]
