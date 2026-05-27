# Legal Risk Reduction Strategies for LIPSA

**Status**: Analysis + Implementation direction (May 2026)

**Chosen Direction**: Hybrid model (Option 2) + Strengthened Guardrails (Option 3)

We are keeping powerful public scraping capabilities while:
- Making lower-risk data sources (Sales Navigator, official exports, etc.) first-class over time.
- Adding mandatory purpose / lawful basis capture on every collection job.
- Recording data source type on every job for better auditability and risk tiering.

### Current Implementation Status

- `lipsa import sales-nav <csv>` — First lower-risk importer (Sales Navigator people exports)
- All imports go through the same job + purpose + audit system as scraping jobs
- `lipsa jobs list / show / export` fully support imported data
- Purpose capture is enforced for imports (stronger than public scrape in current flow)  
**Context**: Follow-up to the original design (design-doc-08598f72.md) after the user asked "how can we make it legal?"

## Honest Assessment

The core functionality of LIPSA — automated searching and collection of public LinkedIn posts by arbitrary keyword or hashtag — is **very difficult to make fully compliant** with LinkedIn's current User Agreement for most users and use cases.

LinkedIn's Section 8.2 "Don’ts" (still active as of 2026) explicitly bans:
> "software, devices, scripts, robots or any other means to scrape or copy the Services"

Commercial providers (Apify, Bright Data, etc.) do **not** change this fundamental legal reality. As documented in the original design:
- You (the end user) remain the data controller.
- You direct the queries.
- You receive and store the personal data.
- Providers shift liability downstream via their AUPs/DPAs.

Recent enforcement (Proxycurl 2025 shutdown, KASPR €240k CNIL fine, etc.) shows LinkedIn is actively pursuing both direct scrapers and companies that facilitate large-scale collection.

**Conclusion**: The current architecture (commercial scraping providers + heavy disclaimers) is a *risk mitigation* strategy, not a *compliance* strategy.

---

## Options to Make LIPSA Lower Risk / More Defensible

Ranked roughly from most protective to least change to the current vision.

### 1. Fundamental Pivot (Highest Legal Protection)

**Change the product from "search public LinkedIn" to "process data you have legitimate rights to".**

**Recommended new primary positioning**:
> "The local-first tool for analyzing your own LinkedIn data and Sales Navigator exports."

**Key changes**:
- Make importing official LinkedIn/Sales Navigator exports the **primary** happy path.
- Support:
  - LinkedIn "Download your data" archives
  - Sales Navigator list exports (CSV)
  - Company page admin exports (where user has legitimate access)
- Treat broad public post scraping via Apify/Bright Data as a **secondary, heavily gated, research-only** feature (or remove it entirely for v1).
- Add strong "lawful basis" capture at import time (e.g., "This is my own data / my company's data / I have consent from these individuals").

**Pros**: Much easier to defend. Aligns with "data minimization" and "purpose limitation". Lower chance of account bans for the end user.
**Cons**: Loses the "search any hashtag on all of LinkedIn" magic that motivated the original request.

This direction was already flagged as Open Question #4 in the original design ("read-only Sales Navigator export importer as a lower-risk complementary path").

### 2. Hybrid Model (Good Compromise)

Keep some public search capability but make lower-risk inputs first-class and more prominent.

**Specific recommendations**:
- Build a first-class **Sales Navigator Importer** module (addressing the open question).
- Add official LinkedIn API support for data the user owns (Company Updates, etc.).
- Keep Apify/Bright Data support but:
  - Mark it clearly as "Higher Risk – Public Data Only"
  - Require an additional purpose declaration before enabling the feature
  - Limit volume more aggressively by default
  - Add prominent "This may still violate ToS" messaging even after the general legal ack
- In the UI/CLI, surface the risk tier of each data source.

This gives users a path to do useful work with meaningfully lower legal exposure while still offering the powerful public search capability for those who accept the risk.

### 3. Strengthen Guardrails on the Current Scraping Path (If Keeping Broad Collection)

If the primary goal remains broad public post search, the current heavy disclaimer + audit approach is already quite good. You can make it even more defensible:

**High-value additions**:
- Add a mandatory "Intended Use / Lawful Basis" declaration step before the first collection (e.g., "Academic research", "Internal competitive intelligence", "Brand monitoring for my company").
- Record this declaration in the audit log and compliance package export.
- Add jurisdiction-aware warnings (stronger language for EU/UK users due to GDPR).
- Consider a separate End User License Agreement (EULA) / Terms of Service for the tool itself that includes indemnification language (users indemnify the tool authors).
- Add "Research / Non-Commercial Use Only" mode that disables certain features.
- Make the compliance package export extremely strong (currently planned for later PRs).

**Limitation**: These steps make the *tool* more defensible and show good faith. They do **not** make the underlying activity of scraping LinkedIn legal.

### 4. Accept It's a High-Risk Research Tool

Some organizations (certain universities, think tanks, specialized research firms) may be willing to accept the risk for specific narrow purposes, especially if they have legal review and limited volume.

In this case, the current architecture (local-first + mandatory consent + excellent audit trail + "you are responsible" messaging) is already one of the more responsible implementations possible.

You would then double down on:
- Extremely clear positioning ("For sophisticated users with legal review only")
- Strong onboarding that includes "Have you consulted counsel?" gates
- Possibly usage caps or approval processes for higher volumes

---

## Practical Next Steps Recommendation

Given the original request ("search posts on LinkedIn on a certain topic or hashtag"), here is a pragmatic path:

1. **Short term (next 1-2 PRs)**: Keep the current Apify path but implement Open Question #4 — add a solid Sales Navigator export importer. This gives users a meaningfully lower-risk option immediately.

2. **Medium term**: Refactor the data source layer so different sources have different risk tiers and consent requirements. Make "Your Data" sources the default/recommended path.

3. **Long term decision point**: Decide whether the product is primarily:
   - A responsible processor for data users already have rights to, **or**
   - A high-risk but powerful research scraping tool with excellent guardrails.

These two directions pull the architecture in somewhat different directions.

---

## Final Advice

**The single most effective thing you can do** to "make it legal" is to stop (or heavily de-emphasize) automated collection of data from LinkedIn that the user does not have a direct relationship with or explicit permission to collect at scale.

Everything else is damage control.

If you want to pursue one of the directions above (especially pivoting toward Sales Navigator + owned data), I can help redesign the relevant parts of the application (importers, data source model, consent flows, etc.).

Would you like me to:
- Draft a revised product positioning / scope document?
- Start implementing a Sales Navigator export importer as the lower-risk path?
- Strengthen the current legal flows with purpose/lawful basis capture?
- Something else?

Be specific about which direction feels most aligned with your actual needs.