"""
Basic tests for the legal/disclaimer module (PR #1).

These tests verify that the core guardrails work:
- Disclaimer text is present and versioned
- require_acknowledgment() correctly reports no-ack when audit is empty
- Acknowledgment can be recorded and then detected
- Audit events are written to the user data directory
"""

import json
from pathlib import Path

from lipsa.legal.disclaimer import (
    DISCLAIMER_VERSION,
    audit_log_event,
    get_audit_log_path,
    get_disclaimer_text,
    get_disclaimer_version,
    get_user_data_dir,
    log_consent_acknowledgment,
    require_acknowledgment,
    reset_acknowledgment_for_testing,
)


def setup_function():
    """Ensure clean state before each test."""
    reset_acknowledgment_for_testing()


def teardown_function():
    """Clean up after each test."""
    reset_acknowledgment_for_testing()


def test_disclaimer_version_and_text_exist():
    """The disclaimer must have a version and substantial text."""
    assert isinstance(DISCLAIMER_VERSION, str)
    assert len(DISCLAIMER_VERSION) >= 8

    text = get_disclaimer_text()
    assert isinstance(text, str)
    assert len(text) > 2000  # Should be a long, serious document
    assert "Section 8.2" in text or "8.2" in text
    assert "data controller" in text.lower()
    assert "no material legal insulation" in text.lower() or "no legal insulation" in text.lower()
    assert DISCLAIMER_VERSION in text


def test_get_version_function_matches_constant():
    assert get_disclaimer_version() == DISCLAIMER_VERSION


def test_user_data_dir_is_created_and_writable(tmp_path, monkeypatch):
    """The user data dir convention must work and be under home or a test override."""
    # We can't easily monkeypatch home in all envs, so just verify it resolves and is usable
    data_dir = get_user_data_dir()
    assert isinstance(data_dir, Path)
    assert data_dir.exists()
    assert data_dir.is_dir()

    # Test that we can write to it (audit log will use it)
    test_file = data_dir / "test_write.tmp"
    test_file.write_text("ok", encoding="utf-8")
    assert test_file.read_text(encoding="utf-8") == "ok"
    test_file.unlink()


def test_require_acknowledgment_returns_false_with_no_prior_ack():
    """Fresh install / reset state must require acknowledgment."""
    assert require_acknowledgment(interactive=False) is False


def test_log_consent_and_require_acknowledgment_detects_it():
    """After logging a consent ack for the current version, require_... must return True."""
    # Simulate user going through the flow
    token = log_consent_acknowledgment(
        user_response="accepted_v" + DISCLAIMER_VERSION,
        query_context="test:legal",
    )
    assert token.startswith("ack_")

    # Now the gate should open
    assert require_acknowledgment(interactive=False) is True


def test_audit_log_event_writes_json_lines():
    """audit_log_event must append valid JSON to the audit log."""
    reset_acknowledgment_for_testing()

    audit_log_event(
        event_type="test_event",
        details={"foo": "bar", "count": 42},
        job_id=None,
    )

    audit_path = get_audit_log_path()
    assert audit_path.exists()

    content = audit_path.read_text(encoding="utf-8").strip()
    lines = [line for line in content.splitlines() if line.strip()]
    assert len(lines) >= 1

    last = json.loads(lines[-1])
    assert last["event_type"] == "test_event"
    assert last["details"]["foo"] == "bar"
    assert "timestamp" in last
    assert last["disclaimer_version"] == DISCLAIMER_VERSION


def test_get_recent_audit_events():
    """Helper to read recent events for compliance package / diagnostics."""
    from lipsa.legal.disclaimer import get_recent_audit_events

    reset_acknowledgment_for_testing()

    audit_log_event("event_one", {"n": 1})
    audit_log_event("event_two", {"n": 2})

    events = get_recent_audit_events(limit=10)
    assert len(events) >= 2
    assert events[-1]["event_type"] == "event_two"
    assert events[-2]["event_type"] == "event_one"


def test_reset_clears_state():
    """reset_acknowledgment_for_testing must make require_ return False again."""
    log_consent_acknowledgment("accepted", "test")
    assert require_acknowledgment(interactive=False) is True

    reset_acknowledgment_for_testing()
    assert require_acknowledgment(interactive=False) is False
