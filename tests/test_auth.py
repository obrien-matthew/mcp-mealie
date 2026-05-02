"""Tests for credential loading."""

import pytest

from mealie_mcp.auth import get_credentials


class TestGetCredentials:
    def test_loads_both(self, monkeypatch):
        monkeypatch.setenv("MEALIE_BASE_URL", "https://mealie.test/")
        monkeypatch.setenv("MEALIE_API_TOKEN", "tok")
        creds = get_credentials()
        assert creds == {"base_url": "https://mealie.test", "token": "tok"}

    def test_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("MEALIE_BASE_URL", "https://mealie.test///")
        monkeypatch.setenv("MEALIE_API_TOKEN", "tok")
        assert get_credentials()["base_url"] == "https://mealie.test"

    def test_missing_url_raises(self, monkeypatch):
        monkeypatch.delenv("MEALIE_BASE_URL", raising=False)
        monkeypatch.setenv("MEALIE_API_TOKEN", "tok")
        with pytest.raises(RuntimeError, match="MEALIE_BASE_URL"):
            get_credentials()

    def test_missing_token_raises(self, monkeypatch):
        monkeypatch.setenv("MEALIE_BASE_URL", "https://mealie.test")
        monkeypatch.delenv("MEALIE_API_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="MEALIE_API_TOKEN"):
            get_credentials()
