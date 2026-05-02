"""Mealie authentication and connection setup."""

import os


def get_credentials() -> dict[str, str]:
    """Load credentials from environment variables.

    Returns dict with 'base_url' and 'token'.
    Raises RuntimeError if MEALIE_BASE_URL or MEALIE_API_TOKEN is missing.
    """
    base_url = os.environ.get("MEALIE_BASE_URL", "").strip()
    token = os.environ.get("MEALIE_API_TOKEN", "").strip()

    if not base_url:
        raise RuntimeError(
            "MEALIE_BASE_URL environment variable is required. "
            "Example: https://mealie.example.com"
        )
    if not token:
        raise RuntimeError(
            "MEALIE_API_TOKEN environment variable is required. "
            "Generate one in Mealie under Profile -> API Tokens."
        )

    return {"base_url": base_url.rstrip("/"), "token": token}
