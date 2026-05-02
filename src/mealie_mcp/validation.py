"""Input validation helpers for Mealie parameters."""


def validate_limit(value: int, max_val: int = 50) -> int:
    """Clamp a limit parameter to the range [1, max_val]."""
    return max(1, min(value, max_val))
