"""
Parquet exporter for LIPSA results.

Excellent for large datasets and data science workflows.
Requires `pyarrow` (optional dependency).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from lipsa.exporters.base import BaseExporter, ExportResult
from lipsa.models.post import Post


class ParquetExporter(BaseExporter):
    """Export posts to Parquet format."""

    format_name = "parquet"
    file_extension = ".parquet"

    def export(
        self,
        records: Iterable[Post],
        output_path: str | Path,
        job_metadata: dict[str, Any] | None = None,
    ) -> ExportResult:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            raise RuntimeError(
                "Parquet export requires the 'pyarrow' package.\n"
                "Install it with: pip install pyarrow"
            ) from None

        output_path = Path(output_path).with_suffix(self.file_extension)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        records_list = [self._prepare_record(post) for post in records]

        if not records_list:
            # Create empty parquet file
            table = pa.table({})
            pq.write_table(table, output_path)
            return ExportResult(output_path=output_path, format=self.format_name, record_count=0)

        # Convert to PyArrow table (handles nested structures reasonably well)
        table = pa.Table.from_pylist(records_list)
        pq.write_table(table, output_path, compression="snappy")

        return ExportResult(
            output_path=output_path,
            format=self.format_name,
            record_count=len(records_list),
            metadata=job_metadata,
        )
