"""
Configuration and secrets management for LIPSA.

PR #3 introduces secure storage of provider API tokens using the `keyring` library
(OS secure credential store: Windows Credential Manager, macOS Keychain, Linux Secret Service, etc.).

This keeps secrets out of plaintext config files and environment variables where possible.
"""

from __future__ import annotations

import keyring

SERVICE_NAME = "lipsa"


def get_provider_token(provider: str) -> str | None:
    """
    Retrieve an API token for a provider from the system keyring.

    Example providers: "apify", "brightdata"
    """
    return keyring.get_password(SERVICE_NAME, f"{provider}_token")


def set_provider_token(provider: str, token: str) -> None:
    """Store a provider token securely in the system keyring."""
    keyring.set_password(SERVICE_NAME, f"{provider}_token", token)


def delete_provider_token(provider: str) -> None:
    """Remove a stored provider token."""
    try:
        keyring.delete_password(SERVICE_NAME, f"{provider}_token")
    except keyring.errors.PasswordDeleteError:
        pass  # token didn't exist


def get_apify_token() -> str | None:
    """Convenience helper for the primary backend in PR #3."""
    return get_provider_token("apify")


def require_apify_token() -> str:
    """
    Return the Apify token or raise a clear error.

    Used by the Apify backend before any API calls.
    """
    token = get_apify_token()
    if not token:
        raise RuntimeError(
            "Apify API token not found.\n"
            "Set it with:  lipsa config set-token apify YOUR_TOKEN\n"
            "Or use the keyring directly for your OS."
        )
    return token
