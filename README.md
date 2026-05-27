# LIPSA – LinkedIn Post Search & Collection Application

> **Local-first tool for searching and collecting public LinkedIn posts by keyword or hashtag, with strong legal, ethical, and audit guardrails.**

**Status**: Alpha (PR #1 complete – project bootstrap + legal foundations only)

---

## ⚠️ CRITICAL LEGAL WARNING

**Using this tool (or any automated means) to access LinkedIn almost certainly violates LinkedIn's User Agreement.**

LinkedIn's User Agreement **Section 8.2 "Don’ts"** (effective November 2025) explicitly prohibits:

> "software, devices, scripts, robots or any other means to scrape or copy the Services, or to use any data mining, robots, or similar data gathering and extraction methods"

**Consequences can include:**
- Permanent account termination (personal and company pages)
- IP and device fingerprint bans
- Civil lawsuits (see hiQ Labs v. LinkedIn and 2025 enforcement actions)
- Regulatory fines under GDPR/CCPA (example: €240,000 CNIL fine against KASPR in 2025)

**Commercial scraping providers (Apify, Bright Data, etc.) provide no legal protection.** You remain the data controller. You are fully responsible.

**This tool makes the risks explicit and auditable. It does not reduce them.**

Before using LIPSA for anything real, **consult qualified legal counsel** in your jurisdiction.

---

## What is LIPSA?

LIPSA (LinkedIn Post Search Application) is being built as a responsible, local-first alternative to ad-hoc scripts and fragmented commercial tools. It prioritizes:

- **Local data ownership** (everything stays on your machine by default)
- **Mandatory, versioned consent + immutable local audit trail**
- **Commercial providers as the primary (safer) backend** (self-scraping is feature-flagged and heavily discouraged)
- **Rich filtering, structured data, and flexible exports** (CSV, Excel, JSON, Parquet, Google Sheets)
- **No engagement automation or contact enrichment features** (those belong in a completely different, higher-risk category)

See the full design document for architecture, data model, risks, and the 9-PR implementation plan:
`design/design-doc-08598f72.md`

---

## Current Status (PR #1 – May 2026)

**This repository started completely empty.**

As of the design exploration on 2026-05-27, the workspace contained **zero files** except an empty `design/` subdirectory (verified via `list_dir` and PowerShell `Get-ChildItem -Recurse -Force`).

PR #1 delivers:
- Modern Python project layout (`src/lipsa/`)
- Strong legal disclaimer module that **must** be called before any collection logic
- Working CLI entrypoint (`lipsa`) with `legal show` / `legal ack` commands
- `lipsa import sales-nav` for lower-risk Sales Navigator CSV imports
- `lipsa jobs list / show / export` with purpose and data source tracking
- Audit logging (JSON Lines + DB) to `~/.lipsa/audit.log` and `~/.lipsa/lipsa.db`
- Prominent warnings on every invocation
- No collection or scraping code (by design)

**You can already run the legal gate today.**

---

## Installation (Development)

```bash
# Clone the repo
git clone <your-repo-url>
cd "LinkedIn Post Scraper"

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify the CLI works
lipsa --help
lipsa --version
```

The first time you run any `lipsa` command you will see the high-risk banner.

---

## Usage (PR #1 – Legal Gate Only)

```bash
# View the full current disclaimer
lipsa legal show

# Read the risks and record your explicit acknowledgment
lipsa legal ack

# Import from a lower-risk source (Sales Navigator export)
lipsa import sales-nav my-export.csv --purpose "Recruiting research for my company - legitimate interest"

# Placeholder search command (enforces the legal gate)
lipsa search "#generative-ai" --max-results 50
# → Will tell you the feature is not implemented yet in PR #1
```

All future collection commands (`search`, scheduled jobs, etc.) will route through the same legal layer.

---

## User Data Directory

LIPSA stores everything under `~/.lipsa/` (or `%USERPROFILE%\.lipsa\` on Windows):

- `audit.log` – append-only JSON Lines audit trail (PR #1)
- `lipsa.db` – SQLite database (PR #2+)
- Future: config, exports, etc.

Deleting this directory completely removes all LIPSA state (except any exports you deliberately saved elsewhere).

---

## Design Principles (from the approved design)

1. **Local-first** – You own the data and the liability.
2. **Commercial providers first** – Apify + Bright Data (self-managed Playwright is disabled by default and heavily warned against).
3. **Mandatory consent + audit** – No silent or background operation without explicit recorded acknowledgment.
4. **No engagement features** – Search and collect only.
5. **Transparency** – Every risk is surfaced in the UI, README, and code.

---

## Roadmap (High Level)

See the full **PR Plan** in `design/design-doc-08598f72.md` (bottom of the document).

- PR #1 (this): Legal foundations + CLI skeleton ✅
- PR #2: Data models + SQLite
- PR #3: Apify backend
- PR #4: Full one-off search CLI + exports (first usable version)
- PR #5+: Scheduling, Bright Data, optional web UI, etc.

After PR #4 you will have a working tool for ad-hoc research with proper safeguards.

---

## Contributing

This project is in early alpha. The highest priority right now is legal safety and correctness of the consent/audit model.

If you are a lawyer, data protection expert, or have deep experience with platform ToS enforcement, your review of the disclaimer text and consent flows would be extremely valuable.

Please open issues or discussions before submitting code that touches the legal layer.

---

## License

MIT License – see [LICENSE](LICENSE) file.

**Additional notice**: The MIT license does **not** protect you from LinkedIn's claims or regulatory action. The extra warnings in this README and in the `lipsa legal` commands are the real legal interface of the project.

---

## Acknowledgments

This design and implementation were created following a rigorous design-review-revise loop (design ID `08598f72`) that explicitly researched LinkedIn's current (2026) API capabilities, ToS, enforcement history, and commercial provider options.

The goal is to give researchers, analysts, and other legitimate users a better tool than ad-hoc scripts — while being brutally honest about the risks.

**Use responsibly. Or better: don't use it for anything that could get you (or your organization) in serious trouble.**
