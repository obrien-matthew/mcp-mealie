"""Tests for MCP server setup."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from mealie_mcp.server import (
    mcp,
    set_recipe_ingredients,
    set_recipe_instructions,
    set_recipe_notes,
)


class TestServerCreation:
    def test_server_exists(self):
        assert mcp is not None

    def test_server_name(self):
        assert mcp.name == "mcp-mealie"


class TestRegisteredTools:
    EXPECTED = {
        # diagnostics
        "get_about",
        "whoami",
        # recipes
        "list_recipes",
        "get_recipe",
        "create_recipe",
        "create_recipe_from_url",
        "update_recipe",
        "delete_recipe",
        "set_recipe_rating",
        "set_recipe_ingredients",
        "set_recipe_ingredients_parsed",
        "set_recipe_instructions",
        "set_recipe_notes",
        "parse_recipe_ingredients",
        # cookbooks
        "list_cookbooks",
        "get_cookbook",
        "create_cookbook",
        "update_cookbook",
        "delete_cookbook",
        # meal plans
        "list_mealplans",
        "get_mealplan",
        "create_mealplan",
        "update_mealplan",
        "delete_mealplan",
        # meal plan rules
        "list_mealplan_rules",
        "get_mealplan_rule",
        "create_mealplan_rule",
        "update_mealplan_rule",
        "delete_mealplan_rule",
        # shopping lists
        "list_shopping_lists",
        "get_shopping_list",
        "create_shopping_list",
        "update_shopping_list",
        "delete_shopping_list",
        "add_recipe_to_shopping_list",
        "remove_recipe_from_shopping_list",
        # shopping items
        "list_shopping_items",
        "get_shopping_item",
        "create_shopping_item",
        "create_shopping_items_bulk",
        "update_shopping_item",
        "delete_shopping_item",
        # parser
        "parse_ingredient",
        "parse_ingredients",
        # categories
        "list_categories",
        "get_category",
        "create_category",
        "update_category",
        "delete_category",
        # tags
        "list_tags",
        "get_tag",
        "create_tag",
        "update_tag",
        "delete_tag",
        # tools
        "list_tools",
        "get_tool",
        "create_tool",
        "update_tool",
        "delete_tool",
        # foods
        "list_foods",
        "get_food",
        "create_food",
        "update_food",
        "delete_food",
        # units
        "list_units",
        "get_unit",
        "create_unit",
        "update_unit",
        "delete_unit",
        # labels
        "list_labels",
        "get_label",
        "create_label",
        "update_label",
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


@pytest.fixture
def mock_client():
    """Patch _get_client to return a MagicMock; yield the mock."""
    fake = MagicMock()
    fake.update_recipe.return_value = {"slug": "soup", "name": "Soup"}
    with patch("mealie_mcp.server._get_client", return_value=fake):
        yield fake


class TestSetRecipeIngredients:
    def test_builds_patch(self, mock_client):
        set_recipe_ingredients("soup", json.dumps(["1 cup flour", "2 eggs"]))
        slug, patch_arg = mock_client.update_recipe.call_args.args
        assert slug == "soup"
        assert patch_arg == {
            "recipeIngredient": [
                {
                    "note": "1 cup flour",
                    "display": "1 cup flour",
                    "originalText": "1 cup flour",
                },
                {"note": "2 eggs", "display": "2 eggs", "originalText": "2 eggs"},
            ]
        }

    def test_rejects_empty(self, mock_client):
        result = set_recipe_ingredients("soup", "[]")
        assert "cannot be empty" in result
        mock_client.update_recipe.assert_not_called()

    def test_rejects_non_strings(self, mock_client):
        result = set_recipe_ingredients("soup", "[1, 2]")
        assert "JSON array of strings" in result
        mock_client.update_recipe.assert_not_called()


class TestSetRecipeInstructions:
    def test_builds_patch(self, mock_client):
        set_recipe_instructions("soup", json.dumps(["Boil water", "Add carrots"]))
        _, patch_arg = mock_client.update_recipe.call_args.args
        assert "recipeInstructions" in patch_arg
        steps = patch_arg["recipeInstructions"]
        assert len(steps) == 2
        assert [s["text"] for s in steps] == ["Boil water", "Add carrots"]
        # Each step must carry the full RecipeStep shape Mealie's PATCH
        # validator expects (a step missing id/title/summary/refs
        # caused 500 TypeError on the server).
        for step in steps:
            assert step["title"] == ""
            assert step["summary"] == ""
            assert step["ingredientReferences"] == []
            # id is a uuid4 string
            uuid.UUID(step["id"])

    def test_auto_splits_title_colon_text(self, mock_client):
        set_recipe_instructions(
            "soup",
            json.dumps(["Press the tofu: Drain and wrap in a clean towel."]),
        )
        _, patch_arg = mock_client.update_recipe.call_args.args
        step = patch_arg["recipeInstructions"][0]
        assert step["title"] == "Press the tofu"
        assert step["text"] == "Drain and wrap in a clean towel."

    def test_does_not_split_long_or_punctuated_prefix(self, mock_client):
        # "Bring..." is too long and contains a period, so the colon
        # later in the line shouldn't trigger an auto-split.
        prose = (
            "Bring a large pot of water to a rolling boil. Cook noodles "
            "until al dente: usually 4-5 minutes."
        )
        set_recipe_instructions("soup", json.dumps([prose]))
        _, patch_arg = mock_client.update_recipe.call_args.args
        step = patch_arg["recipeInstructions"][0]
        assert step["title"] == ""
        assert step["text"] == prose

    def test_accepts_explicit_dict_form(self, mock_client):
        set_recipe_instructions(
            "soup",
            json.dumps(
                [{"title": "Cook the steak: medium rare", "text": "Sear 3 min/side"}]
            ),
        )
        _, patch_arg = mock_client.update_recipe.call_args.args
        step = patch_arg["recipeInstructions"][0]
        # Dict form is taken verbatim -- no auto-split on the title.
        assert step["title"] == "Cook the steak: medium rare"
        assert step["text"] == "Sear 3 min/side"

    def test_rejects_empty(self, mock_client):
        result = set_recipe_instructions("soup", "[]")
        assert "cannot be empty" in result
        mock_client.update_recipe.assert_not_called()


class TestSetRecipeNotes:
    def test_builds_patch_with_titles(self, mock_client):
        set_recipe_notes(
            "soup",
            json.dumps(
                [
                    {"title": "Tip", "text": "Toast spices first."},
                    {"text": "Untitled note."},
                ]
            ),
        )
        _, patch_arg = mock_client.update_recipe.call_args.args
        assert patch_arg == {
            "notes": [
                {"text": "Toast spices first.", "title": "Tip"},
                {"text": "Untitled note."},
            ]
        }

    def test_rejects_missing_text(self, mock_client):
        result = set_recipe_notes("soup", json.dumps([{"title": "T"}]))
        assert "with at least 'text'" in result
        mock_client.update_recipe.assert_not_called()
