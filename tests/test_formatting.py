"""Tests for response formatters."""

from mealie_mcp.formatting import (
    format_about,
    format_cookbook,
    format_food,
    format_label,
    format_mealplan,
    format_mealplan_rule,
    format_page,
    format_parsed_ingredient,
    format_recipe_attach,
    format_recipe_full,
    format_recipe_page,
    format_recipe_summary,
    format_shopping_item,
    format_shopping_list,
    format_taxonomy_item,
    format_unit,
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


class TestFormatPage:
    def test_uses_provided_formatter(self):
        out = format_page(
            {
                "page": 2,
                "per_page": 10,
                "total": 1,
                "total_pages": 1,
                "items": [{"x": 1}],
            },
            lambda i: {"x_doubled": i["x"] * 2},
        )
        assert out["page"] == 2
        assert out["items"] == [{"x_doubled": 2}]


class TestFormatCookbook:
    def test_extracts(self):
        out = format_cookbook(
            {
                "id": "u",
                "name": "Quick Meals",
                "slug": "quick-meals",
                "description": "<30m",
                "queryFilterString": "totalTime < 30",
                "public": False,
                "position": 1,
            }
        )
        assert out["query_filter_string"] == "totalTime < 30"
        assert out["public"] is False


class TestFormatMealplan:
    def test_freeform(self):
        out = format_mealplan(
            {
                "id": 5,
                "date": "2026-05-02",
                "entryType": "dinner",
                "title": "Leftovers",
                "text": "fridge",
            }
        )
        assert out["entry_type"] == "dinner"
        assert out["recipe"] is None

    def test_with_recipe(self):
        out = format_mealplan(
            {
                "id": 6,
                "date": "2026-05-02",
                "entryType": "dinner",
                "recipe": {"slug": "tacos", "name": "Tacos"},
            }
        )
        assert out["recipe"]["slug"] == "tacos"


class TestFormatMealplanRule:
    def test_extracts(self):
        out = format_mealplan_rule(
            {
                "id": "u",
                "day": "monday",
                "entryType": "dinner",
                "queryFilterString": "tags.name = quick",
            }
        )
        assert out["query_filter_string"] == "tags.name = quick"


class TestFormatShopping:
    def test_list(self):
        out = format_shopping_list(
            {
                "id": "lid",
                "name": "Groceries",
                "listItems": [{"id": "a", "note": "carrots"}],
                "recipeReferences": [{"recipeId": "r1", "recipeQuantity": 1}],
            }
        )
        assert out["list_items"][0]["note"] == "carrots"
        assert out["recipe_references"][0]["recipe_id"] == "r1"

    def test_item(self):
        out = format_shopping_item(
            {
                "id": "i",
                "shoppingListId": "lid",
                "note": "carrots",
                "quantity": 2.0,
                "checked": False,
                "isFood": False,
                "display": "carrots, 2",
            }
        )
        assert out["display"] == "carrots, 2"
        assert out["checked"] is False

    def test_recipe_attach_filters_to_added_items(self):
        response = {
            "name": "Groceries",
            "labelSettings": [{"labelId": "noise"} for _ in range(20)],
            "listItems": [
                {
                    "id": "old",
                    "display": "stale item",
                    "recipeReferences": [{"recipeId": "other"}],
                },
                {
                    "id": "new",
                    "display": "new shrimp",
                    "recipeReferences": [{"recipeId": "r1"}],
                },
            ],
        }
        out = format_recipe_attach("L", "r1", response)
        assert out == {
            "list_id": "L",
            "recipe_id": "r1",
            "items_added": 1,
            "items": [
                {
                    "id": "new",
                    "shopping_list_id": None,
                    "note": None,
                    "quantity": None,
                    "checked": None,
                    "is_food": None,
                    "food_id": None,
                    "unit_id": None,
                    "label_id": None,
                    "position": None,
                    "display": "new shrimp",
                }
            ],
        }

    def test_recipe_attach_handles_non_dict(self):
        out = format_recipe_attach("L", "r1", None)
        assert out == {"list_id": "L", "recipe_id": "r1", "items_added": 0}


class TestFormatTaxonomy:
    def test_item(self):
        out = format_taxonomy_item({"id": "i", "name": "Mains", "slug": "mains"})
        assert out["slug"] == "mains"

    def test_food(self):
        out = format_food(
            {
                "id": "f",
                "name": "carrot",
                "pluralName": "carrots",
                "label": {"id": "l", "name": "produce"},
            }
        )
        assert out["plural_name"] == "carrots"
        assert out["label"]["name"] == "produce"

    def test_food_no_label(self):
        out = format_food({"id": "f", "name": "carrot"})
        assert out["label"] is None

    def test_unit(self):
        out = format_unit(
            {
                "id": "u",
                "name": "tablespoon",
                "abbreviation": "tbsp",
                "fraction": True,
                "useAbbreviation": True,
            }
        )
        assert out["abbreviation"] == "tbsp"
        assert out["fraction"] is True

    def test_label(self):
        out = format_label(
            {"id": "l", "name": "produce", "color": "#0a0", "groupId": "g"}
        )
        assert out["color"] == "#0a0"


class TestFormatParsedIngredient:
    def test_extracts(self):
        out = format_parsed_ingredient(
            {
                "input": "2 tbsp olive oil",
                "confidence": {"average": 0.97},
                "ingredient": {
                    "quantity": 2.0,
                    "unit": {"name": "tablespoon"},
                    "food": {"name": "olive oil"},
                    "note": "",
                    "display": "2 tbsp olive oil",
                },
            }
        )
        assert out["ingredient"]["unit"] == "tablespoon"
        assert out["ingredient"]["food"] == "olive oil"

    def test_handles_nulls(self):
        out = format_parsed_ingredient(
            {"input": "salt", "ingredient": {"food": None, "unit": None}}
        )
        assert out["ingredient"]["unit"] is None
        assert out["ingredient"]["food"] is None
