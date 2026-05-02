"""Tests for input validation helpers."""

import pytest

from mealie_mcp.validation import (
    validate_limit,
    validate_non_empty,
    validate_page,
    validate_slug,
    validate_url,
)


class TestValidateLimit:
    def test_within_range(self):
        assert validate_limit(20) == 20

    def test_clamps_to_min(self):
        assert validate_limit(0) == 1

    def test_clamps_to_max(self):
        assert validate_limit(500) == 100

    def test_custom_max(self):
        assert validate_limit(80, max_val=50) == 50


class TestValidatePage:
    def test_passthrough(self):
        assert validate_page(3) == 3

    def test_clamps_zero(self):
        assert validate_page(0) == 1

    def test_clamps_negative(self):
        assert validate_page(-5) == 1


class TestValidateSlug:
    def test_simple_slug(self):
        assert validate_slug("chocolate-chip-cookies") == "chocolate-chip-cookies"

    def test_lowercases(self):
        assert validate_slug("Apple-Pie") == "apple-pie"

    def test_strips(self):
        assert validate_slug("  pizza  ") == "pizza"

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="empty"):
            validate_slug("")

    def test_rejects_spaces(self):
        with pytest.raises(ValueError, match="lowercase"):
            validate_slug("apple pie")

    def test_rejects_underscore(self):
        with pytest.raises(ValueError, match="lowercase"):
            validate_slug("apple_pie")


class TestValidateUrl:
    def test_https(self):
        assert validate_url("https://example.com/recipe") == "https://example.com/recipe"

    def test_http(self):
        assert validate_url("http://example.com") == "http://example.com"

    def test_strips(self):
        assert validate_url("  https://x.com  ") == "https://x.com"

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="empty"):
            validate_url("")

    def test_rejects_no_scheme(self):
        with pytest.raises(ValueError, match="http"):
            validate_url("example.com")


class TestValidateNonEmpty:
    def test_passthrough(self):
        assert validate_non_empty("hello", "name") == "hello"

    def test_strips(self):
        assert validate_non_empty("  x  ", "name") == "x"

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="name cannot be empty"):
            validate_non_empty("   ", "name")
