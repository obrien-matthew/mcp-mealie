"""Tests for MCP server setup."""

from mealie_mcp.server import mcp


class TestServerCreation:
    def test_server_exists(self):
        assert mcp is not None

    def test_server_name(self):
        assert mcp.name == "mcp-mealie"


class TestRegisteredTools:
    EXPECTED = {
        "get_about",
        "whoami",
        "list_recipes",
        "get_recipe",
        "create_recipe",
        "create_recipe_from_url",
        "update_recipe",
        "delete_recipe",
    }

    async def _tool_names(self) -> set[str]:
        tools = await mcp.list_tools()
        return {t.name for t in tools}

    def test_all_tools_registered(self):
        import asyncio

        names = asyncio.run(self._tool_names())
        missing = self.EXPECTED - names
        assert not missing, f"missing tools: {missing}"
