"""
Legal disclaimer, consent acknowledgment, and basic audit helper for LIPSA.

This module is the foundation of the legal/ethical guardrails required by the design.
It must be called before any operation that performs (or would perform) automated
access to LinkedIn.

Key principles (from design):
- No material legal insulation from commercial providers.
- Explicit, timestamped, versioned user acknowledgment is mandatory.
- Audit trail is append-only and user-owned (local).
- "You are the data controller. You are responsible."

For PR #1 the audit is file-based (JSON Lines in ~/.lipsa/audit.log).
Later PRs will migrate this to the structured audit_events table.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# =============================================================================
# DISCLAIMER VERSION
# Bump this (and update the text) whenever the legal language or risks change.
# The CLI and future job system will force re-acknowledgment when the version
# changes for a given job definition.
# =============================================================================
DISCLAIMER_VERSION: str = "2026-05-27"


# =============================================================================
# FULL CURRENT DISCLAIMER TEXT
# This is the canonical text shown to every user. It is deliberately long and
# direct. It is embedded in the binary so it cannot be "lost" or separated from
# the tool.
# =============================================================================
_DISCLAIMER_TEXT: str = f"""\
LIPSA – LinkedIn Post Search & Collection Application
Disclaimer & Legal Warning (Version {DISCLAIMER_VERSION})

================================================================================
CRITICAL: YOU ARE ALMOST CERTAINLY VIOLATING LINKEDIN'S TERMS OF SERVICE
================================================================================

LinkedIn's User Agreement (Section 8.2 "Don’ts", effective November 2025 and
still current) explicitly prohibits:

    "software, devices, scripts, robots or any other means to scrape or copy
     the Services, or to use any data mining, robots, or similar data gathering
     and extraction methods"

Using LIPSA (or ANY automated tool) to access, search, or collect LinkedIn posts,
profiles, or other content is a direct violation of LinkedIn's User Agreement.
Consequences documented by LinkedIn and in public enforcement actions include:

- Immediate and permanent account termination (personal + company)
- IP address blocking and device fingerprint bans
- Civil lawsuits for breach of contract (see hiQ Labs v. LinkedIn precedents
  and 2022 settlement with $500k judgment + permanent injunction on contract claims)
- Regulatory action under GDPR/CCPA and equivalent laws (example: CNIL fine of
  €240,000 against KASPR in 2025 for scraping LinkedIn data)

Recent enforcement (2025):
- Proxycurl / Nubela: Federal lawsuit, July 2025 shutdown + consent judgment
  requiring deletion of data and permanent injunction.
- Multiple other scrapers and enrichment services have received cease-and-desist
  letters, account terminations, and legal demands.

================================================================================
COMMERCIAL PROVIDERS PROVIDE NO LEGAL INSULATION
================================================================================

Using Apify, Bright Data, or any other commercial scraping service does NOT
protect you. You remain the data controller under GDPR/CCPA. You direct the
queries. You receive and store the personal data (names, opinions, affiliations,
post content). Providers' Acceptable Use Policies and Data Processing Agreements
require YOU to warrant that your use is lawful and often require you to indemnify
the provider.

LIPSA makes this explicit. It does not create "legal distance."

================================================================================
YOUR RESPONSIBILITIES (DATA CONTROLLER)
================================================================================

- You are solely responsible for determining whether your collection has a lawful
  basis (consent, legitimate interest, etc.) under applicable data protection law.
- You must honor data subject rights (access, deletion, etc.).
- You must not use collected data for spam, harassment, automated outreach,
  deanonymization, or any purpose that could cause harm.
- You must not scrape authenticated (logged-in) sessions unless you have explicit
  legal advice that it is permissible in your jurisdiction for your specific use
  case (many providers and LinkedIn's own rules prohibit this).

LIPSA contains no features for engagement automation or contact enrichment.
Adding such features yourself dramatically increases your legal exposure.

================================================================================
NO WARRANTY – USE ENTIRELY AT YOUR OWN RISK
================================================================================

This software is provided "AS IS". The authors and contributors accept ZERO
liability for:

- Account bans or loss of LinkedIn access
- Civil claims, injunctions, or damages
- Regulatory fines (GDPR fines can reach 4% of global turnover)
- Data loss, incorrect data, or provider service changes
- Any other direct, indirect, incidental, or consequential damages

Even "public" data on LinkedIn is subject to LinkedIn's contractual terms.
The fact that data is visible in a browser does not make automated collection
legal.

================================================================================
RECOMMENDATION
================================================================================

Before using LIPSA for any real work:

1. Consult qualified legal counsel in your jurisdiction who understands both
   data protection law (GDPR/CCPA/etc.) and platform terms of service.
2. Perform a Data Protection Impact Assessment (DPIA) if you are subject to GDPR.
3. Document your lawful basis for processing.
4. Start with the smallest possible scope and volume.

The existence of this tool does not constitute legal advice.

================================================================================
CONSENT & AUDIT
================================================================================

LIPSA will not perform (or simulate) any LinkedIn access until you have
explicitly acknowledged the above risks for the current disclaimer version.
Acknowledgments are logged locally with timestamp and version in an immutable
audit trail under your control (~/.lipsa/).

You can view the current disclaimer at any time with:
    lipsa legal show

You can record your acknowledgment with:
    lipsa legal ack

Future versions of LIPSA will require re-acknowledgment when this text or the
risk profile changes.

================================================================================
BY USING THIS SOFTWARE YOU AFFIRM THAT:
================================================================================

- You have read and understood this entire disclaimer.
- You understand that you are violating LinkedIn's Terms of Service.
- You accept full personal and organizational responsibility for all
  consequences.
- You have obtained any necessary legal advice for your specific situation.

If you do not accept these terms, do not use LIPSA. Delete it from your system.

================================================================================
"""

# =============================================================================
# USER DATA DIRECTORY
# All local state (future SQLite DB, audit logs, config, exports) lives here.
# This keeps the project clean and makes uninstall trivial.
# =============================================================================
def get_user_data_dir() -> Path:
    """Return the per-user LIPSA data directory (~/.lipsa or %USERPROFILE%\\.lipsa)."""
    if os.name == "nt":
        base = Path(os.environ.get("USERPROFILE", Path.home()))
    else:
        base = Path.home()
    data_dir = base / ".lipsa"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_audit_log_path() -> Path:
    """Path to the append-only JSON Lines audit log used in PR #1."""
    return get_user_data_dir() / "audit.log"


# =============================================================================
# PUBLIC API – These are the functions that must be called before collection
# =============================================================================
def get_disclaimer_text() -> str:
    """Return the full current disclaimer text (for display in CLI / UI)."""
    return _DISCLAIMER_TEXT


def get_disclaimer_version() -> str:
    """Return the current disclaimer version string."""
    return DISCLAIMER_VERSION


def require_acknowledgment(
    interactive: bool = True,
    context: str = "",
) -> bool:
    """
    Check whether the user has a recorded acknowledgment for the *current*
    disclaimer version in this session or recent history.

    For PR #1 this is a simple heuristic (checks last 50 lines of audit.log).
    In later PRs this will query the `audit_events` table with proper
    version + job scoping.

    Returns True only if a matching consent_ack for the current version
    is found in the local audit trail.

    When interactive=True and no ack is found, it will guide the user to run
    `lipsa legal ack`.
    """
    audit_path = get_audit_log_path()
    if not audit_path.exists():
        if interactive:
            _prompt_for_ack(context)
        return False

    current_version = DISCLAIMER_VERSION
    try:
        # Read last N lines (cheap way for PR #1)
        with audit_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-100:]  # last 100 events max
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get("event_type") == "consent_ack":
                    # Check both root level (from log_consent_acknowledgment) and details (from audit_log_event)
                    ver = event.get("disclaimer_version") or event.get("details", {}).get("disclaimer_version")
                    if ver == current_version:
                        return True
            except json.JSONDecodeError:
                continue
    except Exception:
        pass  # If audit is corrupt we treat as "no ack"

    if interactive:
        _prompt_for_ack(context)
    return False


def _prompt_for_ack(context: str) -> None:
    from rich.console import Console
    console = Console()
    console.print(
        "\n[bold red]Legal acknowledgment required for the current disclaimer.[/bold red]"
    )
    console.print(f"Context: {context or 'general use'}")
    console.print(
        "Run [cyan]lipsa legal ack[/cyan] to read the full text and record your acknowledgment.\n"
    )


def log_consent_acknowledgment(
    user_response: str,
    query_context: str = "",
) -> str:
    """
    Record a consent acknowledgment. Returns a compact ack token that can be
    stored against a job definition later.

    This is the function future code (job creation, search, scheduler) must call
    after the user has gone through the interactive prompt.
    """
    timestamp = datetime.now(UTC).isoformat()
    ack_token = f"ack_{DISCLAIMER_VERSION}_{timestamp.replace(':', '').replace('-', '')[:15]}"

    event = {
        "timestamp": timestamp,
        "event_type": "consent_ack",
        "disclaimer_version": DISCLAIMER_VERSION,
        "user_ack": user_response,
        "context": query_context,
        "ack_token": ack_token,
    }
    _append_audit_event(event)
    return ack_token


def audit_log_event(
    event_type: str,
    details: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> None:
    """
    Append a structured audit event (JSON Lines).

    This is the primitive audit helper for PR #1. It will be replaced / augmented
    by the proper `audit_events` table and repository methods in PR #2+.
    """
    event: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "disclaimer_version": DISCLAIMER_VERSION,
    }
    if job_id:
        event["job_id"] = job_id
    if details:
        event["details"] = details

    _append_audit_event(event)


def _append_audit_event(event: dict[str, Any]) -> None:
    """Internal: append one JSON object as a line to the audit log."""
    audit_path = get_audit_log_path()
    # Ensure directory exists (defensive)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def get_recent_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    """Utility for diagnostics and the future compliance package exporter."""
    audit_path = get_audit_log_path()
    if not audit_path.exists():
        return []

    events: list[dict[str, Any]] = []
    try:
        with audit_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines):
            if len(events) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return list(reversed(events))


# =============================================================================
# Convenience for tests and future code
# =============================================================================
def reset_acknowledgment_for_testing() -> None:
    """
    Test helper only. Deletes the local audit log so require_acknowledgment()
    returns False again. Never call in production paths.
    """
    audit_path = get_audit_log_path()
    if audit_path.exists():
        audit_path.unlink()
