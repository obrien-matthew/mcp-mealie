"""Input validation helpers for Mealie parameters."""

import re

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_limit(value: int, max_val: int = 100) -> int:
    """Clamp a limit/per_page parameter to [1, max_val]."""
    return max(1, min(value, max_val))


def validate_page(value: int) -> int:
    """Clamp a page number to [1, inf)."""
    return max(1, value)


def validate_slug(value: str) -> str:
    """Validate a Mealie recipe slug.

    Mealie slugs are lowercase, hyphen-separated, alphanumeric.
    """
    value = value.strip().lower()
    if not value:
        raise ValueError("Slug cannot be empty.")
    if not _SLUG_RE.match(value):
        raise ValueError(
            f"Slug must be lowercase alphanumeric with hyphens, got '{value}'."
        )
    return value


def validate_url(value: str) -> str:
    """Basic validation for a recipe source URL."""
    value = value.strip()
    if not value:
        raise ValueError("URL cannot be empty.")
    if not value.startswith(("http://", "https://")):
        raise ValueError(f"URL must start with http:// or https://, got '{value}'.")
    return value


def validate_non_empty(value: str, field: str) -> str:
    """Ensure a string field is non-empty after stripping."""
    value = value.strip()
    if not value:
        raise ValueError(f"{field} cannot be empty.")
    return value
