"""Tests for MCP server setup."""

from mealie_mcp.server import mcp


class TestServerCreation:
    def test_server_exists(self):
        assert mcp is not None

    def test_server_name(self):
        assert mcp.name == "mcp-mealie"


class TestRegisteredTools:
    EXPECTED = {
        # diagnostics
        "get_about", "whoami",
        # recipes
        "list_recipes", "get_recipe", "create_recipe",
        "create_recipe_from_url", "update_recipe", "delete_recipe",
        # cookbooks
        "list_cookbooks", "get_cookbook", "create_cookbook",
        "update_cookbook", "delete_cookbook",
        # meal plans
        "list_mealplans", "get_mealplan", "create_mealplan",
        "update_mealplan", "delete_mealplan",
        # meal plan rules
        "list_mealplan_rules", "get_mealplan_rule", "create_mealplan_rule",
        "update_mealplan_rule", "delete_mealplan_rule",
        # shopping lists
        "list_shopping_lists", "get_shopping_list", "create_shopping_list",
        "update_shopping_list", "delete_shopping_list",
        "add_recipe_to_shopping_list", "remove_recipe_from_shopping_list",
        # shopping items
        "list_shopping_items", "get_shopping_item", "create_shopping_item",
        "create_shopping_items_bulk", "update_shopping_item",
        "delete_shopping_item",
        # parser
        "parse_ingredient", "parse_ingredients", "parse_recipe_ingredients",
        # categories
        "list_categories", "get_category", "create_category",
        "update_category", "delete_category",
        # tags
        "list_tags", "get_tag", "create_tag", "update_tag", "delete_tag",
        # tools
        "list_tools", "get_tool", "create_tool", "update_tool", "delete_tool",
        # foods
        "list_foods", "get_food", "create_food", "update_food", "delete_food",
        # units
        "list_units", "get_unit", "create_unit", "update_unit", "delete_unit",
        # labels
        "list_labels", "get_label", "create_label", "update_label",
        "delete_label",
    }

    async def _tool_names(self) -> set[str]:
        tools = await mcp.list_tools()
        return {t.name for t in tools}

    def test_all_tools_registered(self):
        import asyncio

        names = asyncio.run(self._tool_names())
        missing = self.EXPECTED - names
        assert not missing, f"missing tools: {missing}"
