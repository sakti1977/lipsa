"""
CSV exporter for LIPSA results.

Produces a clean, flat CSV suitable for analysis in Excel, Google Sheets, R, Python, etc.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from lipsa.exporters.base import BaseExporter, ExportResult
from lipsa.models.post import Post


class CSVExporter(BaseExporter):
    """Export posts to a CSV file."""

    format_name = "csv"
    file_extension = ".csv"

    def export(
        self,
        records: Iterable[Post],
        output_path: str | Path,
        job_metadata: dict[str, Any] | None = None,
    ) -> ExportResult:
        output_path = Path(output_path)
        if not output_path.suffix:
            output_path = output_path.with_suffix(self.file_extension)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        records_list = list(records)
        if not records_list:
            # Write empty file with headers
            with output_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._get_headers())
            return ExportResult(
                output_path=output_path,
                format=self.format_name,
                record_count=0,
                metadata=job_metadata,
            )

        headers = self._get_headers()

        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()

            for post in records_list:
                row = self._prepare_record(post)
                # Flatten some nested structures for CSV friendliness
                row = self._flatten_for_csv(row)
                writer.writerow(row)

        return ExportResult(
            output_path=output_path,
            format=self.format_name,
            record_count=len(records_list),
            metadata=job_metadata,
        )

    def _get_headers(self) -> list[str]:
        """Define a sensible, stable set of columns for CSV export."""
        return [
            "post_urn",
            "url",
            "text",
            "author_name",
            "author_headline",
            "author_profile_url",
            "author_company",
            "posted_at",
            "reactions_count",
            "comments_count",
            "reposts_count",
            "content_type",
            "is_repost",
            "hashtags",
            "mentions",
            # Note: reaction_breakdown, media, and raw_provider_data are complex
            # and intentionally omitted from the default CSV for readability.
            # Users who need them can use the JSON exporter with include_raw=True.
        ]

    def _flatten_for_csv(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert complex fields into CSV-friendly strings."""
        flat = data.copy()

        # Convert lists to comma-separated strings
        for key in ("hashtags", "mentions"):
            if isinstance(flat.get(key), list):
                flat[key] = ", ".join(str(x) for x in flat[key])

        # Convert dicts to simple string representation (or omit)
        for key in ("reaction_breakdown", "media", "raw_provider_data"):
            if key in flat:
                del flat[key]  # Keep CSV clean by default

        return flat
