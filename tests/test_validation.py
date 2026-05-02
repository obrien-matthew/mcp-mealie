"""Tests for input validation helpers."""

import pytest

from mealie_mcp.validation import (
    validate_day_of_week,
    validate_entry_type,
    validate_iso_date,
    validate_limit,
    validate_non_empty,
    validate_page,
    validate_parser,
    validate_slug,
    validate_url,
    validate_uuid,
)

_UUID = "11111111-2222-3333-4444-555555555555"


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


class TestValidateUuid:
    def test_valid(self):
        assert validate_uuid(_UUID) == _UUID

    def test_uppercase_ok(self):
        assert validate_uuid(_UUID.upper()) == _UUID.upper()

    def test_rejects_non_uuid(self):
        with pytest.raises(ValueError, match="UUID"):
            validate_uuid("not-a-uuid")

    def test_uses_field_name(self):
        with pytest.raises(ValueError, match="recipe_id"):
            validate_uuid("nope", "recipe_id")


class TestValidateIsoDate:
    def test_valid(self):
        assert validate_iso_date("2026-05-02") == "2026-05-02"

    def test_rejects_format(self):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            validate_iso_date("05/02/2026")

    def test_rejects_invalid_date(self):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            validate_iso_date("2026-13-99")


class TestValidateEntryType:
    def test_valid(self):
        assert validate_entry_type("Dinner") == "dinner"

    def test_rejects_unknown(self):
        with pytest.raises(ValueError, match="entry_type"):
            validate_entry_type("brunch")


class TestValidateDayOfWeek:
    def test_valid(self):
        assert validate_day_of_week("Friday") == "friday"

    def test_unset_ok(self):
        assert validate_day_of_week("unset") == "unset"

    def test_rejects_unknown(self):
        with pytest.raises(ValueError, match="day"):
            validate_day_of_week("funday")


class TestValidateParser:
    def test_nlp(self):
        assert validate_parser("NLP") == "nlp"

    def test_brute(self):
        assert validate_parser("brute") == "brute"

    def test_rejects_other(self):
        with pytest.raises(ValueError, match="parser"):
            validate_parser("magic")
