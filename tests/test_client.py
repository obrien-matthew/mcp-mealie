"""Tests for the Mealie client."""

from mealie_mcp.client import MealieClient


class TestClient:
    def test_ping(self):
        client = MealieClient()
        assert client.ping() == "pong"
