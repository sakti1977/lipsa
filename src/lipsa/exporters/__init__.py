"""Data exporters for LIPSA results.

These exporters allow users to export collected data (from both public scraping
and lower-risk imports) in various formats.

Supported formats (P4 scope):
- CSV
- JSON / NDJSON
- Excel (openpyxl)
- Parquet (optional, pyarrow)

All exporters should work with the canonical Post model and preserve
important metadata like data_source_type and purpose when possible.
"""

from lipsa.exporters.base import BaseExporter, ExportResult
from lipsa.exporters.csv import CSVExporter
from lipsa.exporters.excel import ExcelExporter
from lipsa.exporters.json import JSONExporter
from lipsa.exporters.parquet import ParquetExporter

__all__ = [
    "BaseExporter",
    "ExportResult",
    "CSVExporter",
    "ExcelExporter",
    "JSONExporter",
    "ParquetExporter",
    "export_posts",
]


def export_posts(
    records,
    output_path: str,
    format: str = "csv",
    include_raw: bool = False,
    job_metadata: dict | None = None,
) -> ExportResult:
    """
    Convenience function to export posts.

    Args:
        records: Iterable of Post objects.
        output_path: Destination file path.
        format: One of 'csv', 'json', 'ndjson'.
        include_raw: Whether to include raw_provider_data.
        job_metadata: Optional metadata to embed (purpose, source, etc.).
    """
    fmt = format.lower()

    if fmt == "csv":
        exporter = CSVExporter(include_raw=include_raw)
    elif fmt == "excel" or fmt == "xlsx":
        exporter = ExcelExporter(include_raw=include_raw)
    elif fmt == "json":
        exporter = JSONExporter(ndjson=False, include_raw=include_raw)
    elif fmt == "ndjson":
        exporter = JSONExporter(ndjson=True, include_raw=include_raw)
    elif fmt == "parquet":
        exporter = ParquetExporter(include_raw=include_raw)
    else:
        raise ValueError(f"Unsupported export format: {format}")

    return exporter.export(records, output_path, job_metadata=job_metadata)

