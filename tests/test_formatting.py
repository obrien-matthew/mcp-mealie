"""Tests for response formatters."""

from mealie_mcp.formatting import format_item


class TestFormatItem:
    def test_formats_item(self):
        result = format_item("test")
        assert result == {"raw": "test"}
