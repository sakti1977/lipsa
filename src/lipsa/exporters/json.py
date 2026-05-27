"""
JSON and NDJSON exporters for LIPSA results.

These are excellent when you want the full fidelity of the data, including
raw_provider_data when requested.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from lipsa.exporters.base import BaseExporter, ExportResult
from lipsa.models.post import Post


class JSONExporter(BaseExporter):
    """Export posts to JSON (array) or NDJSON (one object per line)."""

    format_name = "json"
    file_extension = ".json"

    def __init__(self, ndjson: bool = False, include_raw: bool = False):
        super().__init__(include_raw=include_raw)
        self.ndjson = ndjson
        if ndjson:
            self.format_name = "ndjson"
            self.file_extension = ".ndjson"

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

        records_list = [self._prepare_record(post) for post in records]

        payload: dict[str, Any] = {
            "records": records_list,
            "count": len(records_list),
        }

        if job_metadata:
            payload["job_metadata"] = job_metadata

        with output_path.open("w", encoding="utf-8") as f:
            if self.ndjson:
                # NDJSON: one JSON object per line (great for streaming / big data)
                for record in records_list:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            else:
                # Pretty JSON array
                json.dump(payload, f, indent=2, ensure_ascii=False, default=str)

        return ExportResult(
            output_path=output_path,
            format=self.format_name,
            record_count=len(records_list),
            metadata=job_metadata,
        )
