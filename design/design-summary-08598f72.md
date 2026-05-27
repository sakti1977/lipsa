# Design Summary: LinkedIn Post Search & Collection Application (LIPSA)

**Document ID**: 08598f72  
**Date Produced**: 2026-05-27  
**Related Design**: `design/design-doc-08598f72.md`

## What Was Produced

A complete, senior-engineer-targeted design document (`design/design-doc-08598f72.md`) for a local-first application that enables structured search, filtering, collection, and export of public LinkedIn posts by keyword or hashtag.

The design thoroughly addresses the core constraints:
- Absence of any official LinkedIn API for general public post keyword/hashtag search (only owned/authorized organization content is supported via Marketing APIs).
- Strict LinkedIn ToS prohibition on scraping/automation, with active enforcement (account bans, lawsuits including 2025 Proxycurl-related actions, GDPR fines such as KASPR €240k).
- Significant technical challenges of self-managed automation (Playwright/Puppeteer stealth fragility against fingerprinting, behavioral detection, frequent DOM changes, CAPTCHAs, login walls).
- Need for both one-off interactive use and recurring/scheduled monitoring by researchers, marketers, analysts, and recruiters.

## Key Elements of the Design

**Proposed Solution**: Local-first Python CLI (Typer/Rich) + optional localhost web UI (FastAPI) application. Primary data collection via commercial providers (Apify LinkedIn Post Search actors such as `harvestapi/linkedin-post-search` and `supreme_coder/linkedin-post` — no-cookie variants preferred — plus Bright Data as secondary). Self-managed Playwright backend implemented but **disabled by default** and heavily gated.

**Core Capabilities**:
- Keyword + hashtag search with filters (date posted, min reactions/comments, author type/facets, content type, sort) mirroring and extending LinkedIn UI.
- Structured canonical data model (post URN/URL/text, author details, timestamps, full engagement metrics + breakdowns, media, hashtags, raw provider fidelity).
- One-off + recurring jobs with APScheduler.
- Local SQLite persistence + rich exports (CSV/Excel/JSON/Parquet + compliance audit packages).
- Scraper abstraction layer for provider flexibility.
- Mandatory per-action legal/ethical consent + immutable audit logging.

**Architecture Highlights** (detailed in doc with 4 Mermaid diagrams):
- Clean separation: Legal/Consent → Job Manager/Scheduler → Scraper Interface → Normalizer → Storage → Exporter.
- Quantified expectations: typical workloads (200–2000 posts/search), commercial costs ($5–40/mo), latency, storage footprint.

**Mandatory Sections Included**:
- Thorough **Alternatives Considered** (self-managed Playwright, hosted SaaS, Sales Nav + cleaners, dataset purchases) with explicit trade-off analysis.
- Substantial **Risks & Mitigations** (Critical legal/ToS/GDPR/CFAA risks with specific cases and concrete mitigations).
- Dedicated **Data Ethics & Compliance** section (lawfulness, transparency, minimization, user control principles + built-in tooling).
- **Key Decisions** (7 major architectural choices with rationale, including local-first, commercial-primary, consent gates, etc.).
- Detailed **PR Plan** (9 concrete, ordered, independently reviewable PRs from bootstrap/legal foundations through full GA readiness, with files, dependencies, and value delivered per PR).

**Initial Project State Reference**: The design explicitly documents that the workspace was empty (0 files, only empty `design/` dir) at exploration time on 2026-05-27 (verified via `list_dir` + PowerShell `Get-ChildItem`).

## Research Incorporated

- Official LinkedIn API limitations (2025–2026 developer portal, Marketing APIs, "API Gap" analyses).
- ToS language and enforcement history (hiQ precedent limits, Proxycurl 2025 actions, KASPR fine).
- Detailed provider comparison (Apify actors with ratings/users/pricing, Bright Data dedicated scrapers + compliance certs + pay-per-success, Oxylabs restrictions + KYC, ScrapingBee public non-authenticated support with explicit authenticated sessions prohibition in 2025 AUP).
- Self-managed challenges (fingerprinting, DOM churn, volume limits, maintenance reality from 2025–2026 sources).
- Real LinkedIn UI filters and scraper-extracted fields for accurate data model.

## Files Written

- `design/design-doc-08598f72.md` (full design document, ~5,500 words, production-ready for senior engineering review).
- `design/design-summary-08598f72.md` (this file).

## Next Steps (per Design)

Follow the PR plan sequentially. PR #1 (bootstrap + legal) and PR #4 (usable one-off CLI) deliver immediate value while keeping legal exposure front-and-center. All high-severity risks are addressed with concrete, implementable controls rather than vague statements.

The design is deliberately conservative on self-scraping and explicit about legal realities, consistent with the problem constraints provided.

---

*This summary was generated after full exploration of the (initially empty) workspace and comprehensive research into LinkedIn APIs, ToS, commercial providers, and self-managed automation realities as of 2026.*