"""Tests for input validation helpers."""

from mealie_mcp.validation import validate_limit


class TestValidateLimit:
    def test_within_range(self):
        assert validate_limit(10) == 10

    def test_clamps_to_min(self):
        assert validate_limit(0) == 1

    def test_clamps_to_max(self):
        assert validate_limit(100) == 50
