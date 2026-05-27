"""
Importer for LinkedIn Sales Navigator CSV exports.

Sales Navigator exports are one of the lower-risk ways to get structured
professional data (compared to scraping public posts).

Typical columns in a Sales Nav export:
- First Name, Last Name, Title, Company, LinkedIn URL (or Profile URL),
  Location, About, etc.

This importer normalizes each row into our canonical Post model with:
- content_type = "imported_profile"
- Full original row preserved in raw_provider_data
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from lipsa.importers.base import BaseImporter, ImportResult
from lipsa.models.post import Post


class SalesNavigatorCSVImporter(BaseImporter):
    """Importer for Sales Navigator people exports (CSV)."""

    source_type = "sales_navigator_export"

    def import_from_path(self, path: str) -> ImportResult:
        self.validate_purpose()

        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        items: list[Post] = []
        total_rows = 0
        skipped = 0

        with file_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            for row in reader:
                total_rows += 1
                try:
                    post = self._row_to_post(row, headers)
                    items.append(post)
                except Exception:
                    skipped += 1
                    continue

        return ImportResult(
            items=items,
            source_file=str(file_path),
            source_type=self.source_type,
            total_rows=total_rows,
            skipped_rows=skipped,
            metadata={"original_columns": headers},
        )

    def _row_to_post(self, row: dict[str, str], headers: list[str]) -> Post:
        first = row.get("First Name", "").strip()
        last = row.get("Last Name", "").strip()
        full_name = f"{first} {last}".strip() or "Unknown"

        title = row.get("Title", "") or row.get("Job Title", "")
        company = row.get("Company", "") or row.get("Current Company", "")
        profile_url = (
            row.get("LinkedIn URL")
            or row.get("Profile URL")
            or row.get("URL")
            or "https://www.linkedin.com"
        )

        about = row.get("About", "") or row.get("Summary", "")
        text = f"{title} at {company}".strip()
        if about:
            text += f"\n\n{about[:500]}"

        # Create a stable synthetic URN for deduplication
        url_for_hash = profile_url or f"{full_name}-{company}"
        urn_hash = hashlib.sha256(url_for_hash.encode()).hexdigest()[:16]
        synthetic_urn = f"salesnav:profile:{urn_hash}"

        return Post(
            post_urn=synthetic_urn,
            url=profile_url,
            text=text or "(no details)",
            author_name=full_name,
            author_headline=title or None,
            author_profile_url=profile_url,
            author_company=company or None,
            posted_at=None,  # We don't have reliable dates from exports usually
            content_type="imported_profile",
            raw_provider_data={k: v for k, v in row.items() if v},  # clean empty values
        )
