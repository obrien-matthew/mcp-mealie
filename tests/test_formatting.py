"""Tests for response formatters."""

from mealie_mcp.formatting import (
    format_about,
    format_recipe_full,
    format_recipe_page,
    format_recipe_summary,
    format_user,
)


class TestFormatAbout:
    def test_extracts_fields(self):
        out = format_about(
            {
                "version": "v2.0.0",
                "production": True,
                "demoStatus": False,
                "defaultGroupSlug": "home",
                "allowSignup": False,
                "enableOidc": False,
                "extra": "ignored",
            }
        )
        assert out["version"] == "v2.0.0"
        assert out["production"] is True
        assert out["default_group_slug"] == "home"
        assert "extra" not in out

    def test_handles_missing(self):
        out = format_about({})
        assert out["version"] is None


class TestFormatUser:
    def test_extracts_fields(self):
        out = format_user(
            {
                "id": "u1",
                "username": "matt",
                "fullName": "Matt O",
                "email": "m@x",
                "admin": True,
                "group": "home",
                "household": "main",
                "password": "should-not-leak",
            }
        )
        assert out["username"] == "matt"
        assert out["full_name"] == "Matt O"
        assert "password" not in out


class TestFormatRecipeSummary:
    def test_basic(self):
        out = format_recipe_summary(
            {
                "id": "r1",
                "slug": "tacos",
                "name": "Tacos",
                "description": "yum",
                "recipeYield": "4 servings",
                "totalTime": "30 minutes",
                "rating": 5,
                "tags": [{"name": "dinner"}, {"name": "mexican"}],
                "recipeCategory": [{"name": "Mains"}],
            }
        )
        assert out["slug"] == "tacos"
        assert out["tags"] == ["dinner", "mexican"]
        assert out["categories"] == ["Mains"]

    def test_handles_missing_lists(self):
        out = format_recipe_summary({"slug": "x", "name": "X"})
        assert out["tags"] == []
        assert out["categories"] == []


class TestFormatRecipeFull:
    def test_flattens_ingredients_and_steps(self):
        out = format_recipe_full(
            {
                "slug": "soup",
                "name": "Soup",
                "recipeIngredient": [
                    {"display": "1 cup carrots"},
                    {"note": "salt to taste"},
                ],
                "recipeInstructions": [
                    {"text": "Boil water"},
                    {"text": "Add carrots"},
                ],
                "tools": [{"name": "Pot"}],
            }
        )
        assert out["ingredients"] == ["1 cup carrots", "salt to taste"]
        assert out["instructions"] == ["Boil water", "Add carrots"]
        assert out["tools"] == ["Pot"]


class TestFormatRecipePage:
    def test_summarizes_items(self):
        out = format_recipe_page(
            {
                "page": 1,
                "per_page": 20,
                "total": 2,
                "total_pages": 1,
                "items": [
                    {"slug": "a", "name": "A"},
                    {"slug": "b", "name": "B"},
                ],
            }
        )
        assert out["total"] == 2
        assert [i["slug"] for i in out["items"]] == ["a", "b"]
