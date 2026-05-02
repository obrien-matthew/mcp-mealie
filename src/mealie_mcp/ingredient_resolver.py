"""Bind parser output (string names) to existing food/unit UUIDs.

Mealie's recipe storage requires each ingredient's food and unit to be a
reference to an existing row in the `foods` / `units` tables. The parser
returns names as strings. This module bridges the two.

Match strategy: load the full food and unit indices once per resolver
instance, build a lowercase-keyed dict over name + plural + aliases +
abbreviations, and look up each parser result. If no key matches, create
a new row and add it to the index so subsequent ingredients in the same
batch reuse it.

Two-pass design: callers build a single resolver, run all ingredients
through `to_recipe_ingredient`, then PATCH the recipe in one shot.
"""

from typing import Any

from .client import MealieClient


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


class IngredientResolver:
    """Resolve parsed-ingredient food/unit names to Mealie UUIDs."""

    def __init__(self, client: MealieClient, *, min_confidence: float = 0.5):
        self._client = client
        self._min_confidence = min_confidence
        self._food_index: dict[str, dict[str, Any]] | None = None
        self._unit_index: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    # Index loading
    # ------------------------------------------------------------------

    def _build_food_index(self) -> dict[str, dict[str, Any]]:
        page = self._client.list_foods(page=1, per_page=1000)
        index: dict[str, dict[str, Any]] = {}
        for food in page.get("items") or []:
            for key in self._food_keys(food):
                index.setdefault(key, food)
        return index

    def _build_unit_index(self) -> dict[str, dict[str, Any]]:
        page = self._client.list_units(page=1, per_page=1000)
        index: dict[str, dict[str, Any]] = {}
        for unit in page.get("items") or []:
            for key in self._unit_keys(unit):
                index.setdefault(key, unit)
        return index

    @staticmethod
    def _food_keys(food: dict[str, Any]) -> list[str]:
        keys = [food.get("name"), food.get("pluralName")]
        for alias in food.get("aliases") or []:
            keys.append(alias.get("name") if isinstance(alias, dict) else alias)
        return [_norm(k) for k in keys if k]

    @staticmethod
    def _unit_keys(unit: dict[str, Any]) -> list[str]:
        keys = [
            unit.get("name"),
            unit.get("pluralName"),
            unit.get("abbreviation"),
            unit.get("pluralAbbreviation"),
        ]
        for alias in unit.get("aliases") or []:
            keys.append(alias.get("name") if isinstance(alias, dict) else alias)
        return [_norm(k) for k in keys if k]

    def _foods(self) -> dict[str, dict[str, Any]]:
        if self._food_index is None:
            self._food_index = self._build_food_index()
        return self._food_index

    def _units(self) -> dict[str, dict[str, Any]]:
        if self._unit_index is None:
            self._unit_index = self._build_unit_index()
        return self._unit_index

    # ------------------------------------------------------------------
    # Lookup or create
    # ------------------------------------------------------------------

    def or_create_food(self, name: str) -> dict[str, Any]:
        key = _norm(name)
        if not key:
            raise ValueError("Cannot resolve a food with an empty name.")
        index = self._foods()
        if key in index:
            return index[key]
        created = self._client.create_food({"name": name.strip()})
        for k in self._food_keys(created):
            index.setdefault(k, created)
        return created

    def or_create_unit(self, name: str) -> dict[str, Any]:
        key = _norm(name)
        if not key:
            raise ValueError("Cannot resolve a unit with an empty name.")
        index = self._units()
        if key in index:
            return index[key]
        created = self._client.create_unit({"name": name.strip()})
        for k in self._unit_keys(created):
            index.setdefault(k, created)
        return created

    # ------------------------------------------------------------------
    # Build a recipeIngredient payload
    # ------------------------------------------------------------------

    def to_recipe_ingredient(
        self, parser_response: dict[str, Any], *, original_text: str
    ) -> dict[str, Any]:
        """Map a parse_ingredient response to a Mealie recipeIngredient.

        Mealie's parser returns `food` and `unit` as either strings (food
        name) or objects (`{id, name, ...}` — populated id means Mealie's
        parser already matched against an existing food/unit, in which
        case we use that id directly and skip our resolver lookup).

        On low confidence (or parse failure) returns a free-text note
        ingredient so the recipe still renders the line verbatim.
        """
        ingredient = (parser_response or {}).get("ingredient") or {}
        confidence = (parser_response or {}).get("confidence") or {}

        food_ref = self._coerce_ref(ingredient.get("food"))
        unit_ref = self._coerce_ref(ingredient.get("unit"))
        quantity = ingredient.get("quantity")
        note = ingredient.get("note") or ""
        avg_conf = float(confidence.get("average") or 0.0)

        if avg_conf < self._min_confidence or not food_ref:
            return self._free_text_ingredient(original_text)

        food = self._resolve_ref(food_ref, kind="food")
        unit = self._resolve_ref(unit_ref, kind="unit") if unit_ref else None

        display_parts = [
            str(quantity) if quantity else "",
            unit["name"] if unit else "",
            food["name"],
            note,
        ]
        display = " ".join(p for p in display_parts if p).strip()

        return {
            "quantity": quantity,
            "unit": {"id": unit["id"], "name": unit.get("name", "")} if unit else None,
            "food": {"id": food["id"], "name": food.get("name", "")},
            "note": note,
            "isFood": True,
            "disableAmount": False,
            "display": display,
            "originalText": original_text,
        }

    @staticmethod
    def _coerce_ref(value: Any) -> dict[str, Any] | None:
        """Normalize parser's food/unit value to {id?, name} or None.

        Mealie's parser may return either a string name or a full object
        depending on whether it matched an existing record. We collapse
        to a uniform shape here.
        """
        if not value:
            return None
        if isinstance(value, str):
            name = value.strip()
            return {"name": name} if name else None
        if isinstance(value, dict):
            name = (value.get("name") or "").strip()
            ref: dict[str, Any] = {"name": name}
            if value.get("id"):
                ref["id"] = value["id"]
            return ref if name or ref.get("id") else None
        return None

    def _resolve_ref(self, ref: dict[str, Any], *, kind: str) -> dict[str, Any]:
        """If Mealie already gave us an id, trust it. Otherwise resolve by name."""
        if ref.get("id"):
            return {"id": ref["id"], "name": ref.get("name", "")}
        if kind == "food":
            return self.or_create_food(ref["name"])
        return self.or_create_unit(ref["name"])

    @staticmethod
    def _free_text_ingredient(text: str) -> dict[str, Any]:
        return {
            "quantity": None,
            "unit": None,
            "food": None,
            "note": text,
            "isFood": False,
            "disableAmount": True,
            "display": text,
            "originalText": text,
        }
