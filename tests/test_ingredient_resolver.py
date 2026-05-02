"""Tests for IngredientResolver."""

from unittest.mock import MagicMock

import pytest

from mealie_mcp.ingredient_resolver import IngredientResolver


def _make_client(*, foods=None, units=None) -> MagicMock:
    client = MagicMock()
    client.list_foods.return_value = {"items": foods or []}
    client.list_units.return_value = {"items": units or []}
    return client


def _parser_response(
    *,
    food: str | None,
    unit: str | None,
    quantity: float | None,
    note: str = "",
    confidence: float = 0.99,
) -> dict:
    return {
        "ingredient": {
            "food": food,
            "unit": unit,
            "quantity": quantity,
            "note": note,
        },
        "confidence": {"average": confidence},
    }


class TestFoodIndex:
    def test_matches_name_case_insensitive(self):
        client = _make_client(foods=[{"id": "f1", "name": "Shrimp"}])
        r = IngredientResolver(client)
        out = r.or_create_food("shrimp")
        assert out["id"] == "f1"
        client.create_food.assert_not_called()

    def test_matches_plural_name(self):
        client = _make_client(
            foods=[{"id": "f1", "name": "carrot", "pluralName": "carrots"}]
        )
        r = IngredientResolver(client)
        assert r.or_create_food("carrots")["id"] == "f1"
        client.create_food.assert_not_called()

    def test_matches_alias(self):
        client = _make_client(
            foods=[
                {
                    "id": "f1",
                    "name": "shrimp",
                    "aliases": [{"name": "raw shrimp"}],
                }
            ]
        )
        r = IngredientResolver(client)
        assert r.or_create_food("RAW Shrimp")["id"] == "f1"

    def test_creates_when_missing(self):
        client = _make_client(foods=[])
        client.create_food.return_value = {"id": "f-new", "name": "kale"}
        r = IngredientResolver(client)
        out = r.or_create_food("kale")
        assert out["id"] == "f-new"
        client.create_food.assert_called_once_with({"name": "kale"})

    def test_caches_created_for_subsequent_lookups(self):
        client = _make_client(foods=[])
        client.create_food.return_value = {"id": "f-new", "name": "kale"}
        r = IngredientResolver(client)
        r.or_create_food("kale")
        r.or_create_food("Kale")  # different case, same food
        client.create_food.assert_called_once()


class TestUnitIndex:
    def test_matches_abbreviation(self):
        client = _make_client(
            units=[{"id": "u1", "name": "tablespoon", "abbreviation": "tbsp"}]
        )
        r = IngredientResolver(client)
        assert r.or_create_unit("tbsp")["id"] == "u1"

    def test_matches_plural_abbreviation(self):
        client = _make_client(
            units=[
                {
                    "id": "u1",
                    "name": "tablespoon",
                    "pluralAbbreviation": "tbsps",
                }
            ]
        )
        r = IngredientResolver(client)
        assert r.or_create_unit("tbsps")["id"] == "u1"


class TestToRecipeIngredient:
    def test_binds_food_and_unit(self):
        client = _make_client(
            foods=[{"id": "f1", "name": "shrimp"}],
            units=[{"id": "u1", "name": "pound"}],
        )
        r = IngredientResolver(client)
        out = r.to_recipe_ingredient(
            _parser_response(food="shrimp", unit="pound", quantity=1.0),
            original_text="1 lb shrimp",
        )
        assert out["food"] == {"id": "f1", "name": "shrimp"}
        assert out["unit"] == {"id": "u1", "name": "pound"}
        assert out["quantity"] == 1.0
        assert out["isFood"] is True
        assert out["originalText"] == "1 lb shrimp"

    def test_unitless_ingredient(self):
        client = _make_client(foods=[{"id": "f1", "name": "egg"}])
        r = IngredientResolver(client)
        out = r.to_recipe_ingredient(
            _parser_response(food="egg", unit=None, quantity=2),
            original_text="2 eggs",
        )
        assert out["unit"] is None
        assert out["food"]["id"] == "f1"

    def test_low_confidence_falls_back_to_free_text(self):
        client = _make_client()
        r = IngredientResolver(client, min_confidence=0.5)
        out = r.to_recipe_ingredient(
            _parser_response(
                food="something", unit=None, quantity=None, confidence=0.2
            ),
            original_text="splash of sake for deglazing",
        )
        assert out["food"] is None
        assert out["unit"] is None
        assert out["isFood"] is False
        assert out["note"] == "splash of sake for deglazing"
        assert out["display"] == "splash of sake for deglazing"
        client.create_food.assert_not_called()

    def test_missing_food_name_falls_back(self):
        client = _make_client()
        r = IngredientResolver(client)
        out = r.to_recipe_ingredient(
            _parser_response(food=None, unit=None, quantity=None),
            original_text="??? unparseable line",
        )
        assert out["food"] is None
        client.create_food.assert_not_called()


class TestEmptyName:
    def test_or_create_food_rejects_empty(self):
        client = _make_client()
        r = IngredientResolver(client)
        with pytest.raises(ValueError):
            r.or_create_food("   ")

    def test_or_create_unit_rejects_empty(self):
        client = _make_client()
        r = IngredientResolver(client)
        with pytest.raises(ValueError):
            r.or_create_unit("")
