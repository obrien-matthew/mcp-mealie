"""Response formatters for Mealie data."""

from typing import Any


def format_item(item: Any) -> dict[str, Any]:
    """Format a Mealie item into an LLM-friendly dict."""
    return {"raw": str(item)}
