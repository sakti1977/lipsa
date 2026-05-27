"""
Base class for all data exporters in LIPSA.

Exporters are responsible for taking a list of Post objects (or more generally
any iterable of records) and writing them to a file in a specific format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lipsa.models.post import Post


@dataclass
class ExportResult:
    """Result of an export operation."""

    output_path: Path
    format: str
    record_count: int
    metadata: dict[str, Any] | None = None


class BaseExporter(ABC):
    """Abstract base class for exporters."""

    format_name: str
    file_extension: str

    def __init__(self, include_raw: bool = False):
        """
        Args:
            include_raw: Whether to include the full raw_provider_data in the export.
                         This can make files much larger.
        """
        self.include_raw = include_raw

    @abstractmethod
    def export(
        self,
        records: Iterable[Post],
        output_path: str | Path,
        job_metadata: dict[str, Any] | None = None,
    ) -> ExportResult:
        """
        Export the given records to the specified path.

        Args:
            records: Iterable of Post objects to export.
            output_path: Where to write the file.
            job_metadata: Optional metadata about the job (purpose, data_source_type, etc.)
                         that can be included in the export (e.g. as comments or separate sheet).
        """
        raise NotImplementedError

    def _prepare_record(self, post: Post) -> dict[str, Any]:
        """Convert a Post into a serializable dict, respecting include_raw."""
        data = post.model_dump()

        if not self.include_raw:
            data.pop("raw_provider_data", None)

        # Make some fields more export-friendly
        if data.get("posted_at"):
            data["posted_at"] = str(data["posted_at"])

        return data
