"""
Base class for lower-risk importers.

Importers are responsible for:
- Reading from a file/path
- Normalizing records into the canonical Post model
- Returning metadata about the import (count, source info)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from lipsa.models.post import Post


@dataclass
class ImportResult:
    """Result of an import operation."""

    items: list[Post]
    source_file: str
    source_type: str
    total_rows: int
    skipped_rows: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def imported_count(self) -> int:
        return len(self.items)


class BaseImporter(ABC):
    """Abstract base for all lower-risk data importers."""

    source_type: str  # Must match a DataSourceType value, e.g. "sales_navigator_export"

    def __init__(self, purpose: str | None = None):
        self.purpose = purpose

    @abstractmethod
    def import_from_path(self, path: str) -> ImportResult:
        """Import data from the given file path and return normalized items."""
        raise NotImplementedError

    def validate_purpose(self) -> None:
        """Optional hook for importers to enforce purpose requirements."""
        if not self.purpose or len(self.purpose.strip()) < 10:
            raise ValueError(
                "A meaningful purpose / lawful basis (at least 10 characters) is required "
                "for lower-risk imports."
            )
