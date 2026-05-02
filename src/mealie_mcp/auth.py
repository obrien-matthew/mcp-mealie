"""Mealie authentication and connection setup."""

import os


def get_credentials() -> dict[str, str]:
    """Load credentials from environment variables."""
    api_key = os.environ.get("MEALIE_API_KEY", "")
    return {"api_key": api_key}
