# LIPSA – LinkedIn Post Search & Collection Application

> **Local-first tool for searching and collecting LinkedIn posts via commercial providers or lower-risk imports, with strong legal, ethical, and audit guardrails.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Status](https://img.shields.io/badge/status-alpha-orange)

---

## ⚠️ CRITICAL LEGAL WARNING

**Using this tool (or any automated means) to access LinkedIn almost certainly violates LinkedIn's User Agreement.**

LinkedIn's User Agreement **Section 8.2 "Don’ts"** explicitly prohibits automated scraping and data extraction.

**Consequences can include:**
- Permanent account termination
- Civil lawsuits and regulatory fines (GDPR/CCPA)
- IP and device bans

**Commercial providers (Apify, Bright Data, etc.) provide no legal protection.** You remain the data controller and are fully responsible.

**Before using LIPSA for anything real, consult qualified legal counsel.**

This tool makes risks explicit and auditable. It does **not** make the activity legal.

---

## What is LIPSA?

LIPSA is a local-first Python CLI for responsibly collecting LinkedIn data. It supports two main paths:

- **Higher-risk path**: Public post search via commercial scraping providers (Apify, etc.)
- **Lower-risk path**: Importing data you already have legitimate access to (Sales Navigator exports, LinkedIn data downloads, etc.)

Key features:
- Strong mandatory consent + immutable audit trail
- Purpose / lawful basis tracking on every job
- Flexible exporters (CSV, JSON, Excel, Parquet)
- Job management and compliance package exports

See the design document for the full architecture and legal analysis:
`design/design-doc-08598f72.md`

---

## Current Status

The project has implemented core functionality through an evolved P4 phase, including:
- Legal foundations and consent system
- Data models and SQLite persistence
- Scraper abstraction + Apify backend
- Lower-risk importers (starting with Sales Navigator)
- Rich one-off CLI with `--export`, `--dry-run`, and progress indicators
- Multiple exporters (CSV, JSON, Excel, Parquet)
- `jobs` commands with purpose and data source tracking
- Compliance package export

The tool is usable for research and testing but remains in active development.

---

## Installation

```bash
git clone https://github.com/sakti1977/lipsa.git
cd lipsa

python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows

pip install -e ".[dev]"

lipsa --help
```

---

## Usage Examples

```bash
# Acknowledge legal risks (required)
lipsa legal ack

# Lower-risk import from Sales Navigator
lipsa import sales-nav ./export.csv --purpose "Recruiting research - legitimate interest"

# Public search with export and dry-run
lipsa search "#ai" --max-results 50 --export results.csv --dry-run

# Inspect jobs and export data
lipsa jobs list
lipsa jobs show <job-id>
lipsa jobs export <job-id> --data-format excel
```

---

## Design Principles

1. Local-first data ownership
2. Hybrid support for different risk profiles
3. Mandatory purpose + audit for every collection
4. Transparency about legal risks
5. No engagement or outreach features

---

## License

MIT License – see [LICENSE](LICENSE) file.

**Important**: The license does **not** protect you from LinkedIn enforcement or regulatory action. The warnings in this README and the `lipsa legal` commands are the primary legal interface.

---

## Contributing

Legal safety and audit correctness are the top priorities. Please review the design document and `docs/LEGAL_RISK_REDUCTION.md` before contributing.

If you have legal or data protection expertise, your input on the consent and compliance flows would be especially valuable.
