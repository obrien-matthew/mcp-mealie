"""Input validation helpers for Mealie parameters."""

import re
from datetime import date

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_ENTRY_TYPES = {"breakfast", "lunch", "dinner", "side"}
_DAYS_OF_WEEK = {
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday", "unset",
}
_PARSER_TYPES = {"nlp", "brute"}


def validate_limit(value: int, max_val: int = 100) -> int:
    """Clamp a limit/per_page parameter to [1, max_val]."""
    return max(1, min(value, max_val))


def validate_page(value: int) -> int:
    """Clamp a page number to [1, inf)."""
    return max(1, value)


def validate_slug(value: str) -> str:
    """Validate a Mealie slug (lowercase, hyphenated, alphanumeric)."""
    value = value.strip().lower()
    if not value:
        raise ValueError("Slug cannot be empty.")
    if not _SLUG_RE.match(value):
        raise ValueError(
            f"Slug must be lowercase alphanumeric with hyphens, got '{value}'."
        )
    return value


def validate_url(value: str) -> str:
    """Basic validation for a URL."""
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


def validate_uuid(value: str, field: str = "id") -> str:
    """Validate a UUID string (any case)."""
    value = value.strip()
    if not value:
        raise ValueError(f"{field} cannot be empty.")
    if not _UUID_RE.match(value):
        raise ValueError(f"{field} must be a UUID, got '{value}'.")
    return value


def validate_iso_date(value: str) -> str:
    """Validate a YYYY-MM-DD date string."""
    value = value.strip()
    if not value:
        raise ValueError("date cannot be empty.")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"date must be YYYY-MM-DD, got '{value}'.") from exc
    return value


def validate_entry_type(value: str) -> str:
    """Validate a meal-plan entry type."""
    lower = value.strip().lower()
    if lower not in _ENTRY_TYPES:
        raise ValueError(
            f"entry_type must be one of {sorted(_ENTRY_TYPES)}, got '{value}'."
        )
    return lower


def validate_day_of_week(value: str) -> str:
    """Validate a meal-plan-rule day."""
    lower = value.strip().lower()
    if lower not in _DAYS_OF_WEEK:
        raise ValueError(
            f"day must be one of {sorted(_DAYS_OF_WEEK)}, got '{value}'."
        )
    return lower


def validate_parser(value: str) -> str:
    """Validate the ingredient parser choice."""
    lower = value.strip().lower()
    if lower not in _PARSER_TYPES:
        raise ValueError(
            f"parser must be one of {sorted(_PARSER_TYPES)}, got '{value}'."
        )
    return lower
