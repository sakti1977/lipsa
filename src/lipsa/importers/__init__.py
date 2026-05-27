"""Lower-risk data importers for LIPSA (hybrid approach).

These importers allow users to bring in data from sources they have legitimate
access to (Sales Navigator exports, LinkedIn data downloads, manual CSVs, etc.),
which is significantly lower legal risk than public scraping.
"""

from lipsa.importers.base import BaseImporter, ImportResult
from lipsa.importers.sales_navigator import SalesNavigatorCSVImporter

__all__ = [
    "BaseImporter",
    "ImportResult",
    "SalesNavigatorCSVImporter",
]
