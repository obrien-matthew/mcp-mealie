"""MCP server with Mealie tools."""

import json
import re
import uuid
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import MealieClient, MealieError
from .formatting import (
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
    format_shopping_item,
    format_shopping_list,
    format_taxonomy_item,
    format_unit,
    format_user,
)
from .ingredient_resolver import IngredientResolver
from .validation import (
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

mcp = FastMCP("mcp-mealie")


@mcp.tool()
def get_server_version() -> str:
    """Return the installed version of the mcp-mealie server."""
    try:
        return version("mcp-mealie")
    except PackageNotFoundError:
        return "unknown"


_client: MealieClient | None = None


def _get_client() -> MealieClient:
    global _client
    if _client is None:
        _client = MealieClient()
    return _client


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


def _error(action: str, exc: Exception) -> str:
    if isinstance(exc, MealieError):
        return _dump(
            {"error": action, "message": exc.message, "status": exc.status_code}
        )
    return _dump({"error": action, "message": str(exc)})


# Matches "Title: rest" where the title is a single line, has no internal
# colons or periods, and is short. Used to auto-split step text into a
# title field. Long titles or titles containing punctuation that suggests
# multiple sentences won't match -- those stay as plain text.
_STEP_TITLE_RE = re.compile(r"^([^:.\n]{1,60}):\s+(.+)$", re.DOTALL)


def _build_recipe_step(item: Any) -> dict[str, Any]:
    """Coerce a string or {title, text} dict into a Mealie RecipeStep payload.

    Strings ending in "Title: text" are auto-split. Pass an explicit
    {title: "", text: ...} dict to opt out of auto-splitting.
    """
    if isinstance(item, str):
        match = _STEP_TITLE_RE.match(item)
        title = match.group(1).strip() if match else ""
        text = match.group(2).strip() if match else item
    elif isinstance(item, dict) and "text" in item:
        title = str(item.get("title") or "").strip()
        text = str(item["text"])
    else:
        raise ValueError(
            "each step must be a string or an object with at least 'text'."
        )
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "summary": "",
        "text": text,
        "ingredientReferences": [],
    }


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@mcp.tool()
def get_about() -> str:
    """Return Mealie server version and basic info. Confirms connectivity."""
    try:
        return _dump(format_about(_get_client().about()))
    except Exception as exc:
        return _error("get_about", exc)


@mcp.tool()
def whoami() -> str:
    """Return the user owning the configured API token. Confirms auth works."""
    try:
        return _dump(format_user(_get_client().whoami()))
    except Exception as exc:
        return _error("whoami", exc)


# ---------------------------------------------------------------------------
# Recipes (CRUD)
# ---------------------------------------------------------------------------


@mcp.tool()
def list_recipes(
    search: str = "",
    page: int = 1,
    per_page: int = 20,
    order_by: str = "",
    order_direction: str = "",
) -> str:
    """List recipes with optional search, sorting, and pagination."""
    try:
        data = _get_client().list_recipes(
            search=search or None,
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=100),
            order_by=order_by or None,
            order_direction=order_direction or None,
        )
        return _dump(format_recipe_page(data))
    except Exception as exc:
        return _error("list_recipes", exc)


@mcp.tool()
def get_recipe(slug: str) -> str:
    """Fetch a full recipe by slug, including ingredients and instructions."""
    try:
        slug = validate_slug(slug)
        return _dump(format_recipe_full(_get_client().get_recipe(slug)))
    except Exception as exc:
        return _error("get_recipe", exc)


@mcp.tool()
def create_recipe(name: str) -> str:
    """Create an empty recipe by name. Returns the new slug."""
    try:
        name = validate_non_empty(name, "name")
        slug = _get_client().create_recipe(name)
        return _dump({"slug": slug, "name": name})
    except Exception as exc:
        return _error("create_recipe", exc)


@mcp.tool()
def create_recipe_from_url(url: str, include_tags: bool = False) -> str:
    """Scrape a recipe from a URL using Mealie's scraper. Returns the new slug."""
    try:
        url = validate_url(url)
        slug = _get_client().create_recipe_from_url(url, include_tags=include_tags)
        return _dump({"slug": slug, "source_url": url})
    except Exception as exc:
        return _error("create_recipe_from_url", exc)


@mcp.tool()
def update_recipe(
    slug: str,
    name: str = "",
    description: str = "",
    recipe_yield: str = "",
    prep_time: str = "",
    perform_time: str = "",
    total_time: str = "",
    org_url: str = "",
) -> str:
    """Patch a recipe. Only non-empty fields are sent.

    Note: rating is per-user in Mealie 2.x+ and is not exposed here. Set it
    via the Mealie UI (or a future dedicated tool) against
    POST /api/users/{user_id}/ratings/{slug}.
    """
    try:
        slug = validate_slug(slug)
        patch: dict[str, Any] = {}
        if name:
            patch["name"] = name
        if description:
            patch["description"] = description
        if recipe_yield:
            patch["recipeYield"] = recipe_yield
        if prep_time:
            patch["prepTime"] = prep_time
        if perform_time:
            patch["performTime"] = perform_time
        if total_time:
            patch["totalTime"] = total_time
        if org_url:
            patch["orgURL"] = validate_url(org_url)
        if not patch:
            raise ValueError("update_recipe called with no changes.")
        return _dump(format_recipe_full(_get_client().update_recipe(slug, patch)))
    except Exception as exc:
        return _error("update_recipe", exc)


@mcp.tool()
def delete_recipe(slug: str) -> str:
    """Delete a recipe by slug. This is permanent."""
    try:
        slug = validate_slug(slug)
        _get_client().delete_recipe(slug)
        return _dump({"deleted": slug})
    except Exception as exc:
        return _error("delete_recipe", exc)


@mcp.tool()
def set_recipe_rating(
    slug: str,
    rating: float = -1.0,
    is_favorite: int = -1,
) -> str:
    """Set the calling user's rating and/or favorite flag for a recipe.

    rating: 0-5 (decimals allowed). Pass -1 to leave unchanged.
    is_favorite: 0=remove, 1=add. Pass -1 to leave unchanged.
    """
    try:
        slug = validate_slug(slug)
        rating_val: float | None = rating if rating >= 0 else None
        favorite_val: bool | None = bool(is_favorite) if is_favorite in (0, 1) else None
        if rating_val is None and favorite_val is None:
            raise ValueError("set_recipe_rating called with nothing to change.")
        _get_client().set_recipe_rating(
            slug, rating=rating_val, is_favorite=favorite_val
        )
        return _dump({"slug": slug, "rating": rating_val, "is_favorite": favorite_val})
    except Exception as exc:
        return _error("set_recipe_rating", exc)


@mcp.tool()
def set_recipe_ingredients(slug: str, ingredients_json: str) -> str:
    """Replace a recipe's ingredient list with the given lines.

    `ingredients_json` is a JSON array of strings, one per ingredient
    (e.g. `["1 cup flour", "2 eggs"]`). Each string is stored verbatim;
    the user can re-parse to structured quantity/unit/food in the
    Mealie UI afterward to enable shopping-list integration.
    """
    try:
        slug = validate_slug(slug)
        items = json.loads(ingredients_json)
        if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
            raise ValueError("ingredients_json must be a JSON array of strings.")
        if not items:
            raise ValueError("ingredients_json cannot be empty.")
        recipe_ingredient = [
            {"note": s, "display": s, "originalText": s} for s in items
        ]
        return _dump(
            format_recipe_full(
                _get_client().update_recipe(
                    slug, {"recipeIngredient": recipe_ingredient}
                )
            )
        )
    except Exception as exc:
        return _error("set_recipe_ingredients", exc)


@mcp.tool()
def set_recipe_instructions(slug: str, instructions_json: str) -> str:
    """Replace a recipe's instruction steps with the given lines.

    `instructions_json` is a JSON array. Each element is either:
      - a string ("Boil water"), or
      - an object ({"title": "Boil", "text": "Boil water"}).

    Strings starting with a short "Title: rest" prefix are auto-split:
    "Boil water: bring 4 quarts to a rolling boil" becomes
    {title: "Boil water", text: "bring 4 quarts..."}. Pass the dict
    form with an empty title to opt out of auto-splitting.
    """
    try:
        slug = validate_slug(slug)
        raw = json.loads(instructions_json)
        if not isinstance(raw, list):
            raise ValueError("instructions_json must be a JSON array.")
        if not raw:
            raise ValueError("instructions_json cannot be empty.")
        recipe_instructions = [_build_recipe_step(item) for item in raw]
        return _dump(
            format_recipe_full(
                _get_client().update_recipe(
                    slug, {"recipeInstructions": recipe_instructions}
                )
            )
        )
    except Exception as exc:
        return _error("set_recipe_instructions", exc)


@mcp.tool()
def set_recipe_notes(slug: str, notes_json: str) -> str:
    """Replace a recipe's notes with the given JSON array.

    `notes_json` is a JSON array of `{title, text}` objects. `title`
    is optional; `text` is required. Example:
    `[{"title": "Tip", "text": "Toast the spices first."}]`.
    """
    try:
        slug = validate_slug(slug)
        raw = json.loads(notes_json)
        if not isinstance(raw, list):
            raise ValueError("notes_json must be a JSON array.")
        if not raw:
            raise ValueError("notes_json cannot be empty.")
        notes: list[dict[str, str]] = []
        for n in raw:
            if not isinstance(n, dict) or "text" not in n:
                raise ValueError("each note must be an object with at least 'text'.")
            note: dict[str, str] = {"text": str(n["text"])}
            if n.get("title"):
                note["title"] = str(n["title"])
            notes.append(note)
        return _dump(
            format_recipe_full(_get_client().update_recipe(slug, {"notes": notes}))
        )
    except Exception as exc:
        return _error("set_recipe_notes", exc)


def _parse_and_bind(
    client: MealieClient,
    raw_lines: list[str],
    *,
    min_confidence: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse each line, resolve food/unit IDs, return (recipeIngredient, summary).

    `summary` reports per-line: kind=bound|free_text, food_name, unit_name,
    confidence, original_text. Useful for showing the LLM what was matched.
    """
    parser = validate_parser("nlp")
    parsed_results = client.parse_ingredients(raw_lines, parser=parser)
    resolver = IngredientResolver(client, min_confidence=min_confidence)
    bound: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for line, parsed in zip(raw_lines, parsed_results, strict=True):
        ingredient_payload = resolver.to_recipe_ingredient(parsed, original_text=line)
        bound.append(ingredient_payload)
        food = ingredient_payload.get("food")
        unit = ingredient_payload.get("unit")
        confidence = ((parsed or {}).get("confidence") or {}).get("average")
        summary.append(
            {
                "original_text": line,
                "kind": "bound" if food else "free_text",
                "food": food.get("name") if food else None,
                "unit": unit.get("name") if unit else None,
                "quantity": ingredient_payload.get("quantity"),
                "confidence": confidence,
            }
        )
    return bound, summary


@mcp.tool()
def parse_recipe_ingredients(slug: str, min_confidence: float = 0.5) -> str:
    """Re-parse a recipe's free-text ingredients and bind to food/unit IDs.

    Reads the recipe's current ingredients, runs each line through
    Mealie's NLP parser, looks up matching food / unit records (matching
    on name, plural, abbreviations, and aliases — case-insensitive),
    creates new food / unit records when no match exists, and writes the
    bound result back to the recipe. After this runs, ingredients are
    eligible for shopping-list aggregation.

    Lines whose parsed average confidence falls below `min_confidence`
    are stored as free text (no binding) so quirky lines like
    "splash of sake for deglazing" don't pollute the food catalogue.

    Returns a per-line summary of what was bound vs. left as free text.
    """
    try:
        slug = validate_slug(slug)
        client = _get_client()
        recipe = client.get_recipe(slug)
        raw_lines: list[str] = []
        for ing in recipe.get("recipeIngredient") or []:
            text = (
                ing.get("originalText") or ing.get("display") or ing.get("note") or ""
            )
            if text:
                raw_lines.append(text)
        if not raw_lines:
            raise ValueError("Recipe has no ingredient lines to parse.")
        bound, summary = _parse_and_bind(
            client, raw_lines, min_confidence=min_confidence
        )
        client.update_recipe(slug, {"recipeIngredient": bound})
        return _dump({"slug": slug, "ingredients": summary})
    except Exception as exc:
        return _error("parse_recipe_ingredients", exc)


@mcp.tool()
def set_recipe_ingredients_parsed(
    slug: str, ingredients_json: str, min_confidence: float = 0.5
) -> str:
    """Like set_recipe_ingredients, but parses each line and binds food/unit IDs.

    `ingredients_json` is a JSON array of strings. Each is run through
    Mealie's NLP parser; recognized food / unit names are matched
    against the existing taxonomy (or created if not present), so the
    resulting recipe is shopping-list-aggregation-ready.

    Lines whose parsed average confidence falls below `min_confidence`
    are stored as free text.

    Returns a per-line summary of what was bound vs. left as free text.
    """
    try:
        slug = validate_slug(slug)
        items = json.loads(ingredients_json)
        if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
            raise ValueError("ingredients_json must be a JSON array of strings.")
        if not items:
            raise ValueError("ingredients_json cannot be empty.")
        client = _get_client()
        bound, summary = _parse_and_bind(client, items, min_confidence=min_confidence)
        client.update_recipe(slug, {"recipeIngredient": bound})
        return _dump({"slug": slug, "ingredients": summary})
    except Exception as exc:
        return _error("set_recipe_ingredients_parsed", exc)


# ---------------------------------------------------------------------------
# Cookbooks
# ---------------------------------------------------------------------------


@mcp.tool()
def list_cookbooks(page: int = 1, per_page: int = 50) -> str:
    """List cookbooks (saved recipe filters) for the current household."""
    try:
        data = _get_client().list_cookbooks(
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=100),
        )
        return _dump(format_page(data, format_cookbook))
    except Exception as exc:
        return _error("list_cookbooks", exc)


@mcp.tool()
def get_cookbook(cookbook_id: str) -> str:
    """Fetch a cookbook by UUID."""
    try:
        cookbook_id = validate_uuid(cookbook_id, "cookbook_id")
        return _dump(format_cookbook(_get_client().get_cookbook(cookbook_id)))
    except Exception as exc:
        return _error("get_cookbook", exc)


@mcp.tool()
def create_cookbook(
    name: str,
    description: str = "",
    query_filter_string: str = "",
    public: bool = False,
) -> str:
    """Create a cookbook. `query_filter_string` is the Mealie filter DSL."""
    try:
        name = validate_non_empty(name, "name")
        body: dict[str, Any] = {"name": name, "public": public}
        if description:
            body["description"] = description
        if query_filter_string:
            body["queryFilterString"] = query_filter_string
        return _dump(format_cookbook(_get_client().create_cookbook(body)))
    except Exception as exc:
        return _error("create_cookbook", exc)


@mcp.tool()
def update_cookbook(
    cookbook_id: str,
    name: str = "",
    description: str = "",
    query_filter_string: str = "",
    public: int = -1,
) -> str:
    """Patch a cookbook. Use public=1 to make public, public=0 to unpublish."""
    try:
        cookbook_id = validate_uuid(cookbook_id, "cookbook_id")
        patch: dict[str, Any] = {}
        if name:
            patch["name"] = name
        if description:
            patch["description"] = description
        if query_filter_string:
            patch["queryFilterString"] = query_filter_string
        if public in (0, 1):
            patch["public"] = bool(public)
        if not patch:
            raise ValueError("update_cookbook called with no changes.")
        return _dump(format_cookbook(_get_client().update_cookbook(cookbook_id, patch)))
    except Exception as exc:
        return _error("update_cookbook", exc)


@mcp.tool()
def delete_cookbook(cookbook_id: str) -> str:
    """Delete a cookbook by UUID."""
    try:
        cookbook_id = validate_uuid(cookbook_id, "cookbook_id")
        _get_client().delete_cookbook(cookbook_id)
        return _dump({"deleted": cookbook_id})
    except Exception as exc:
        return _error("delete_cookbook", exc)


# ---------------------------------------------------------------------------
# Meal plans
# ---------------------------------------------------------------------------


@mcp.tool()
def list_mealplans(
    start_date: str = "",
    end_date: str = "",
    page: int = 1,
    per_page: int = 50,
) -> str:
    """List meal-plan entries, optionally bounded by start_date/end_date."""
    try:
        sd = validate_iso_date(start_date) if start_date else None
        ed = validate_iso_date(end_date) if end_date else None
        data = _get_client().list_mealplans(
            start_date=sd,
            end_date=ed,
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=200),
        )
        return _dump(format_page(data, format_mealplan))
    except Exception as exc:
        return _error("list_mealplans", exc)


@mcp.tool()
def get_mealplan(mealplan_id: int) -> str:
    """Fetch a meal-plan entry by numeric id."""
    try:
        return _dump(format_mealplan(_get_client().get_mealplan(mealplan_id)))
    except Exception as exc:
        return _error("get_mealplan", exc)


@mcp.tool()
def create_mealplan(
    date: str,
    entry_type: str = "dinner",
    title: str = "",
    text: str = "",
    recipe_id: str = "",
) -> str:
    """Create a meal-plan entry.

    Supply either `recipe_id` (UUID) for a recipe entry, or `title`/`text`
    for a freeform entry. `entry_type` is one of: breakfast, lunch, dinner, side.
    """
    try:
        body: dict[str, Any] = {
            "date": validate_iso_date(date),
            "entryType": validate_entry_type(entry_type),
        }
        if title:
            body["title"] = title
        if text:
            body["text"] = text
        if recipe_id:
            body["recipeId"] = validate_uuid(recipe_id, "recipe_id")
        if not (recipe_id or title):
            raise ValueError("Provide either recipe_id or title for the meal plan.")
        return _dump(format_mealplan(_get_client().create_mealplan(body)))
    except Exception as exc:
        return _error("create_mealplan", exc)


@mcp.tool()
def update_mealplan(
    mealplan_id: int,
    date: str = "",
    entry_type: str = "",
    title: str = "",
    text: str = "",
    recipe_id: str = "",
) -> str:
    """Patch a meal-plan entry. Only non-empty fields are sent."""
    try:
        patch: dict[str, Any] = {}
        if date:
            patch["date"] = validate_iso_date(date)
        if entry_type:
            patch["entryType"] = validate_entry_type(entry_type)
        if title:
            patch["title"] = title
        if text:
            patch["text"] = text
        if recipe_id:
            patch["recipeId"] = validate_uuid(recipe_id, "recipe_id")
        if not patch:
            raise ValueError("update_mealplan called with no changes.")
        return _dump(format_mealplan(_get_client().update_mealplan(mealplan_id, patch)))
    except Exception as exc:
        return _error("update_mealplan", exc)


@mcp.tool()
def delete_mealplan(mealplan_id: int) -> str:
    """Delete a meal-plan entry by id."""
    try:
        _get_client().delete_mealplan(mealplan_id)
        return _dump({"deleted": mealplan_id})
    except Exception as exc:
        return _error("delete_mealplan", exc)


# ---------------------------------------------------------------------------
# Meal plan rules
# ---------------------------------------------------------------------------


@mcp.tool()
def list_mealplan_rules(page: int = 1, per_page: int = 50) -> str:
    """List meal-plan rules used by the random-meal generator."""
    try:
        data = _get_client().list_mealplan_rules(
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=100),
        )
        return _dump(format_page(data, format_mealplan_rule))
    except Exception as exc:
        return _error("list_mealplan_rules", exc)


@mcp.tool()
def get_mealplan_rule(rule_id: str) -> str:
    """Fetch a meal-plan rule by UUID."""
    try:
        rule_id = validate_uuid(rule_id, "rule_id")
        return _dump(format_mealplan_rule(_get_client().get_mealplan_rule(rule_id)))
    except Exception as exc:
        return _error("get_mealplan_rule", exc)


@mcp.tool()
def create_mealplan_rule(
    day: str = "unset",
    entry_type: str = "dinner",
    query_filter_string: str = "",
) -> str:
    """Create a meal-plan rule.

    `day` is monday..sunday or "unset" (any day).
    `entry_type` is breakfast/lunch/dinner/side.
    `query_filter_string` is the Mealie filter DSL (e.g. `tags.name = "quick"`).
    """
    try:
        body = {
            "day": validate_day_of_week(day),
            "entryType": validate_entry_type(entry_type),
            "queryFilterString": query_filter_string,
        }
        return _dump(format_mealplan_rule(_get_client().create_mealplan_rule(body)))
    except Exception as exc:
        return _error("create_mealplan_rule", exc)


@mcp.tool()
def update_mealplan_rule(
    rule_id: str,
    day: str = "",
    entry_type: str = "",
    query_filter_string: str = "",
) -> str:
    """Patch a meal-plan rule."""
    try:
        rule_id = validate_uuid(rule_id, "rule_id")
        patch: dict[str, Any] = {}
        if day:
            patch["day"] = validate_day_of_week(day)
        if entry_type:
            patch["entryType"] = validate_entry_type(entry_type)
        if query_filter_string:
            patch["queryFilterString"] = query_filter_string
        if not patch:
            raise ValueError("update_mealplan_rule called with no changes.")
        return _dump(
            format_mealplan_rule(_get_client().update_mealplan_rule(rule_id, patch))
        )
    except Exception as exc:
        return _error("update_mealplan_rule", exc)


@mcp.tool()
def delete_mealplan_rule(rule_id: str) -> str:
    """Delete a meal-plan rule by UUID."""
    try:
        rule_id = validate_uuid(rule_id, "rule_id")
        _get_client().delete_mealplan_rule(rule_id)
        return _dump({"deleted": rule_id})
    except Exception as exc:
        return _error("delete_mealplan_rule", exc)


# ---------------------------------------------------------------------------
# Shopping lists
# ---------------------------------------------------------------------------


@mcp.tool()
def list_shopping_lists(page: int = 1, per_page: int = 50) -> str:
    """List shopping lists for the current household."""
    try:
        data = _get_client().list_shopping_lists(
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=100),
        )
        return _dump(format_page(data, format_shopping_list))
    except Exception as exc:
        return _error("list_shopping_lists", exc)


@mcp.tool()
def get_shopping_list(list_id: str) -> str:
    """Fetch a shopping list by UUID, including its items."""
    try:
        list_id = validate_uuid(list_id, "list_id")
        return _dump(format_shopping_list(_get_client().get_shopping_list(list_id)))
    except Exception as exc:
        return _error("get_shopping_list", exc)


@mcp.tool()
def create_shopping_list(name: str) -> str:
    """Create a shopping list with the given name."""
    try:
        name = validate_non_empty(name, "name")
        return _dump(
            format_shopping_list(_get_client().create_shopping_list({"name": name}))
        )
    except Exception as exc:
        return _error("create_shopping_list", exc)


@mcp.tool()
def update_shopping_list(list_id: str, name: str = "") -> str:
    """Patch a shopping list. Currently supports renaming."""
    try:
        list_id = validate_uuid(list_id, "list_id")
        patch: dict[str, Any] = {}
        if name:
            patch["name"] = name
        if not patch:
            raise ValueError("update_shopping_list called with no changes.")
        return _dump(
            format_shopping_list(_get_client().update_shopping_list(list_id, patch))
        )
    except Exception as exc:
        return _error("update_shopping_list", exc)


@mcp.tool()
def delete_shopping_list(list_id: str) -> str:
    """Delete a shopping list by UUID."""
    try:
        list_id = validate_uuid(list_id, "list_id")
        _get_client().delete_shopping_list(list_id)
        return _dump({"deleted": list_id})
    except Exception as exc:
        return _error("delete_shopping_list", exc)


@mcp.tool()
def add_recipe_to_shopping_list(list_id: str, recipe_id: str, scale: int = 1) -> str:
    """Add a recipe's ingredients to a shopping list. `scale` multiplies amounts."""
    try:
        list_id = validate_uuid(list_id, "list_id")
        recipe_id = validate_uuid(recipe_id, "recipe_id")
        result = _get_client().add_recipe_to_shopping_list(
            list_id, recipe_id, scale=scale if scale != 1 else None
        )
        return _dump(format_recipe_attach(list_id, recipe_id, result))
    except Exception as exc:
        return _error("add_recipe_to_shopping_list", exc)


@mcp.tool()
def remove_recipe_from_shopping_list(list_id: str, recipe_id: str) -> str:
    """Remove a recipe's ingredients from a shopping list."""
    try:
        list_id = validate_uuid(list_id, "list_id")
        recipe_id = validate_uuid(recipe_id, "recipe_id")
        _get_client().remove_recipe_from_shopping_list(list_id, recipe_id)
        return _dump({"list_id": list_id, "recipe_id": recipe_id, "removed": True})
    except Exception as exc:
        return _error("remove_recipe_from_shopping_list", exc)


# ---------------------------------------------------------------------------
# Shopping items
# ---------------------------------------------------------------------------


@mcp.tool()
def list_shopping_items(list_id: str = "", page: int = 1, per_page: int = 100) -> str:
    """List shopping items, optionally filtered to one shopping list."""
    try:
        lid = validate_uuid(list_id, "list_id") if list_id else None
        data = _get_client().list_shopping_items(
            list_id=lid,
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=200),
        )
        return _dump(format_page(data, format_shopping_item))
    except Exception as exc:
        return _error("list_shopping_items", exc)


@mcp.tool()
def get_shopping_item(item_id: str) -> str:
    """Fetch a shopping item by UUID."""
    try:
        item_id = validate_uuid(item_id, "item_id")
        return _dump(format_shopping_item(_get_client().get_shopping_item(item_id)))
    except Exception as exc:
        return _error("get_shopping_item", exc)


@mcp.tool()
def create_shopping_item(
    list_id: str,
    note: str = "",
    quantity: float = 0.0,
    is_food: bool = False,
    food_id: str = "",
    unit_id: str = "",
    label_id: str = "",
) -> str:
    """Create a single shopping item on a list.

    Free-form items: pass `note` (e.g. "carrots, 2 lb").
    Structured items: set is_food=true and pass `food_id`, optional `unit_id`.
    """
    try:
        list_id = validate_uuid(list_id, "list_id")
        body: dict[str, Any] = {
            "shoppingListId": list_id,
            "isFood": is_food,
            "quantity": quantity,
        }
        if note:
            body["note"] = note
        if food_id:
            body["foodId"] = validate_uuid(food_id, "food_id")
        if unit_id:
            body["unitId"] = validate_uuid(unit_id, "unit_id")
        if label_id:
            body["labelId"] = validate_uuid(label_id, "label_id")
        result = _get_client().create_shopping_item(body)
        if isinstance(result, dict) and "createdItems" in result:
            created = result.get("createdItems") or []
            if len(created) == 1:
                return _dump(format_shopping_item(created[0]))
            return _dump([format_shopping_item(i) for i in created])
        if isinstance(result, list):
            return _dump([format_shopping_item(i) for i in result])
        return _dump(format_shopping_item(result))
    except Exception as exc:
        return _error("create_shopping_item", exc)


@mcp.tool()
def create_shopping_items_bulk(items_json: str) -> str:
    """Bulk-create shopping items from a JSON array.

    `items_json` is a JSON array of item objects. Each item must include
    `shoppingListId` (UUID); `note` and `quantity` are typical optional fields.
    """
    try:
        items = json.loads(items_json)
        if not isinstance(items, list) or not items:
            raise ValueError("items_json must be a non-empty JSON array.")
        result = _get_client().create_shopping_items_bulk(items)
        if isinstance(result, dict) and "createdItems" in result:
            created = result.get("createdItems") or []
            return _dump([format_shopping_item(i) for i in created])
        if isinstance(result, list):
            return _dump([format_shopping_item(i) for i in result])
        return _dump(result)
    except Exception as exc:
        return _error("create_shopping_items_bulk", exc)


@mcp.tool()
def update_shopping_item(
    item_id: str,
    note: str = "",
    quantity: float = -1.0,
    checked: int = -1,
    position: int = -1,
    food_id: str = "",
    unit_id: str = "",
    label_id: str = "",
) -> str:
    """Patch a shopping item. checked: 0=unchecked, 1=checked, -1=leave."""
    try:
        item_id = validate_uuid(item_id, "item_id")
        patch: dict[str, Any] = {}
        if note:
            patch["note"] = note
        if quantity >= 0:
            patch["quantity"] = quantity
        if checked in (0, 1):
            patch["checked"] = bool(checked)
        if position >= 0:
            patch["position"] = position
        if food_id:
            patch["foodId"] = validate_uuid(food_id, "food_id")
        if unit_id:
            patch["unitId"] = validate_uuid(unit_id, "unit_id")
        if label_id:
            patch["labelId"] = validate_uuid(label_id, "label_id")
        if not patch:
            raise ValueError("update_shopping_item called with no changes.")
        return _dump(
            format_shopping_item(_get_client().update_shopping_item(item_id, patch))
        )
    except Exception as exc:
        return _error("update_shopping_item", exc)


@mcp.tool()
def delete_shopping_item(item_id: str) -> str:
    """Delete a shopping item by UUID."""
    try:
        item_id = validate_uuid(item_id, "item_id")
        _get_client().delete_shopping_item(item_id)
        return _dump({"deleted": item_id})
    except Exception as exc:
        return _error("delete_shopping_item", exc)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


@mcp.tool()
def parse_ingredient(text: str, parser: str = "nlp") -> str:
    """Parse a single ingredient string into structured quantity/unit/food.

    `parser` is "nlp" (default, CRF model) or "brute" (regex fallback).
    """
    try:
        text = validate_non_empty(text, "text")
        parser = validate_parser(parser)
        return _dump(
            format_parsed_ingredient(
                _get_client().parse_ingredient(text, parser=parser)
            )
        )
    except Exception as exc:
        return _error("parse_ingredient", exc)


@mcp.tool()
def parse_ingredients(ingredients_json: str, parser: str = "nlp") -> str:
    """Parse many ingredient strings. `ingredients_json` is a JSON string array."""
    try:
        items = json.loads(ingredients_json)
        if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
            raise ValueError("ingredients_json must be a JSON array of strings.")
        if not items:
            raise ValueError("ingredients_json cannot be empty.")
        parser = validate_parser(parser)
        result = _get_client().parse_ingredients(items, parser=parser)
        return _dump([format_parsed_ingredient(p) for p in result])
    except Exception as exc:
        return _error("parse_ingredients", exc)


# ---------------------------------------------------------------------------
# Taxonomy: shared helpers for category / tag / tool
# ---------------------------------------------------------------------------


def _crud_taxonomy(
    action: str,
    list_fn,
    get_fn,
    create_fn,
    update_fn,
    delete_fn,
    formatter,
):
    """Tuple-up the five CRUD operations for a simple {name} taxonomy resource."""
    return list_fn, get_fn, create_fn, update_fn, delete_fn, formatter


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@mcp.tool()
def list_categories(page: int = 1, per_page: int = 100) -> str:
    """List recipe categories."""
    try:
        data = _get_client().list_categories(
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=200),
        )
        return _dump(format_page(data, format_taxonomy_item))
    except Exception as exc:
        return _error("list_categories", exc)


@mcp.tool()
def get_category(category_id: str) -> str:
    """Fetch a category by UUID."""
    try:
        category_id = validate_uuid(category_id, "category_id")
        return _dump(format_taxonomy_item(_get_client().get_category(category_id)))
    except Exception as exc:
        return _error("get_category", exc)


@mcp.tool()
def create_category(name: str) -> str:
    """Create a category."""
    try:
        name = validate_non_empty(name, "name")
        return _dump(
            format_taxonomy_item(_get_client().create_category({"name": name}))
        )
    except Exception as exc:
        return _error("create_category", exc)


@mcp.tool()
def update_category(category_id: str, name: str) -> str:
    """Rename a category by UUID."""
    try:
        category_id = validate_uuid(category_id, "category_id")
        name = validate_non_empty(name, "name")
        return _dump(
            format_taxonomy_item(
                _get_client().update_category(category_id, {"name": name})
            )
        )
    except Exception as exc:
        return _error("update_category", exc)


@mcp.tool()
def delete_category(category_id: str) -> str:
    """Delete a category by UUID."""
    try:
        category_id = validate_uuid(category_id, "category_id")
        _get_client().delete_category(category_id)
        return _dump({"deleted": category_id})
    except Exception as exc:
        return _error("delete_category", exc)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tags(page: int = 1, per_page: int = 100) -> str:
    """List recipe tags."""
    try:
        data = _get_client().list_tags(
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=200),
        )
        return _dump(format_page(data, format_taxonomy_item))
    except Exception as exc:
        return _error("list_tags", exc)


@mcp.tool()
def get_tag(tag_id: str) -> str:
    """Fetch a tag by UUID."""
    try:
        tag_id = validate_uuid(tag_id, "tag_id")
        return _dump(format_taxonomy_item(_get_client().get_tag(tag_id)))
    except Exception as exc:
        return _error("get_tag", exc)


@mcp.tool()
def create_tag(name: str) -> str:
    """Create a tag."""
    try:
        name = validate_non_empty(name, "name")
        return _dump(format_taxonomy_item(_get_client().create_tag({"name": name})))
    except Exception as exc:
        return _error("create_tag", exc)


@mcp.tool()
def update_tag(tag_id: str, name: str) -> str:
    """Rename a tag by UUID."""
    try:
        tag_id = validate_uuid(tag_id, "tag_id")
        name = validate_non_empty(name, "name")
        return _dump(
            format_taxonomy_item(_get_client().update_tag(tag_id, {"name": name}))
        )
    except Exception as exc:
        return _error("update_tag", exc)


@mcp.tool()
def delete_tag(tag_id: str) -> str:
    """Delete a tag by UUID."""
    try:
        tag_id = validate_uuid(tag_id, "tag_id")
        _get_client().delete_tag(tag_id)
        return _dump({"deleted": tag_id})
    except Exception as exc:
        return _error("delete_tag", exc)


# ---------------------------------------------------------------------------
# Tools (kitchen tools)
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tools(page: int = 1, per_page: int = 100) -> str:
    """List kitchen tools."""
    try:
        data = _get_client().list_tools(
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=200),
        )
        return _dump(format_page(data, format_taxonomy_item))
    except Exception as exc:
        return _error("list_tools", exc)


@mcp.tool()
def get_tool(tool_id: str) -> str:
    """Fetch a kitchen tool by UUID."""
    try:
        tool_id = validate_uuid(tool_id, "tool_id")
        return _dump(format_taxonomy_item(_get_client().get_tool(tool_id)))
    except Exception as exc:
        return _error("get_tool", exc)


@mcp.tool()
def create_tool(name: str) -> str:
    """Create a kitchen tool."""
    try:
        name = validate_non_empty(name, "name")
        return _dump(format_taxonomy_item(_get_client().create_tool({"name": name})))
    except Exception as exc:
        return _error("create_tool", exc)


@mcp.tool()
def update_tool(tool_id: str, name: str) -> str:
    """Rename a kitchen tool by UUID."""
    try:
        tool_id = validate_uuid(tool_id, "tool_id")
        name = validate_non_empty(name, "name")
        return _dump(
            format_taxonomy_item(_get_client().update_tool(tool_id, {"name": name}))
        )
    except Exception as exc:
        return _error("update_tool", exc)


@mcp.tool()
def delete_tool(tool_id: str) -> str:
    """Delete a kitchen tool by UUID."""
    try:
        tool_id = validate_uuid(tool_id, "tool_id")
        _get_client().delete_tool(tool_id)
        return _dump({"deleted": tool_id})
    except Exception as exc:
        return _error("delete_tool", exc)


# ---------------------------------------------------------------------------
# Foods
# ---------------------------------------------------------------------------


@mcp.tool()
def list_foods(page: int = 1, per_page: int = 100) -> str:
    """List ingredient foods."""
    try:
        data = _get_client().list_foods(
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=200),
        )
        return _dump(format_page(data, format_food))
    except Exception as exc:
        return _error("list_foods", exc)


@mcp.tool()
def get_food(food_id: str) -> str:
    """Fetch a food by UUID."""
    try:
        food_id = validate_uuid(food_id, "food_id")
        return _dump(format_food(_get_client().get_food(food_id)))
    except Exception as exc:
        return _error("get_food", exc)


@mcp.tool()
def create_food(
    name: str,
    plural_name: str = "",
    description: str = "",
    label_id: str = "",
) -> str:
    """Create a food (ingredient)."""
    try:
        name = validate_non_empty(name, "name")
        body: dict[str, Any] = {"name": name}
        if plural_name:
            body["pluralName"] = plural_name
        if description:
            body["description"] = description
        if label_id:
            body["labelId"] = validate_uuid(label_id, "label_id")
        return _dump(format_food(_get_client().create_food(body)))
    except Exception as exc:
        return _error("create_food", exc)


@mcp.tool()
def update_food(
    food_id: str,
    name: str = "",
    plural_name: str = "",
    description: str = "",
    label_id: str = "",
) -> str:
    """Patch a food."""
    try:
        food_id = validate_uuid(food_id, "food_id")
        patch: dict[str, Any] = {}
        if name:
            patch["name"] = name
        if plural_name:
            patch["pluralName"] = plural_name
        if description:
            patch["description"] = description
        if label_id:
            patch["labelId"] = validate_uuid(label_id, "label_id")
        if not patch:
            raise ValueError("update_food called with no changes.")
        return _dump(format_food(_get_client().update_food(food_id, patch)))
    except Exception as exc:
        return _error("update_food", exc)


@mcp.tool()
def delete_food(food_id: str) -> str:
    """Delete a food by UUID."""
    try:
        food_id = validate_uuid(food_id, "food_id")
        _get_client().delete_food(food_id)
        return _dump({"deleted": food_id})
    except Exception as exc:
        return _error("delete_food", exc)


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


@mcp.tool()
def list_units(page: int = 1, per_page: int = 100) -> str:
    """List units of measure."""
    try:
        data = _get_client().list_units(
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=200),
        )
        return _dump(format_page(data, format_unit))
    except Exception as exc:
        return _error("list_units", exc)


@mcp.tool()
def get_unit(unit_id: str) -> str:
    """Fetch a unit by UUID."""
    try:
        unit_id = validate_uuid(unit_id, "unit_id")
        return _dump(format_unit(_get_client().get_unit(unit_id)))
    except Exception as exc:
        return _error("get_unit", exc)


@mcp.tool()
def create_unit(
    name: str,
    plural_name: str = "",
    abbreviation: str = "",
    plural_abbreviation: str = "",
    description: str = "",
    fraction: int = -1,
    use_abbreviation: int = -1,
) -> str:
    """Create a unit of measure. fraction/use_abbreviation: 0=false, 1=true."""
    try:
        name = validate_non_empty(name, "name")
        body: dict[str, Any] = {"name": name}
        if plural_name:
            body["pluralName"] = plural_name
        if abbreviation:
            body["abbreviation"] = abbreviation
        if plural_abbreviation:
            body["pluralAbbreviation"] = plural_abbreviation
        if description:
            body["description"] = description
        if fraction in (0, 1):
            body["fraction"] = bool(fraction)
        if use_abbreviation in (0, 1):
            body["useAbbreviation"] = bool(use_abbreviation)
        return _dump(format_unit(_get_client().create_unit(body)))
    except Exception as exc:
        return _error("create_unit", exc)


@mcp.tool()
def update_unit(
    unit_id: str,
    name: str = "",
    plural_name: str = "",
    abbreviation: str = "",
    plural_abbreviation: str = "",
    description: str = "",
    fraction: int = -1,
    use_abbreviation: int = -1,
) -> str:
    """Patch a unit."""
    try:
        unit_id = validate_uuid(unit_id, "unit_id")
        patch: dict[str, Any] = {}
        if name:
            patch["name"] = name
        if plural_name:
            patch["pluralName"] = plural_name
        if abbreviation:
            patch["abbreviation"] = abbreviation
        if plural_abbreviation:
            patch["pluralAbbreviation"] = plural_abbreviation
        if description:
            patch["description"] = description
        if fraction in (0, 1):
            patch["fraction"] = bool(fraction)
        if use_abbreviation in (0, 1):
            patch["useAbbreviation"] = bool(use_abbreviation)
        if not patch:
            raise ValueError("update_unit called with no changes.")
        return _dump(format_unit(_get_client().update_unit(unit_id, patch)))
    except Exception as exc:
        return _error("update_unit", exc)


@mcp.tool()
def delete_unit(unit_id: str) -> str:
    """Delete a unit by UUID."""
    try:
        unit_id = validate_uuid(unit_id, "unit_id")
        _get_client().delete_unit(unit_id)
        return _dump({"deleted": unit_id})
    except Exception as exc:
        return _error("delete_unit", exc)


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


@mcp.tool()
def list_labels(page: int = 1, per_page: int = 100) -> str:
    """List multi-purpose labels (used by foods, shopping items, etc.)."""
    try:
        data = _get_client().list_labels(
            page=validate_page(page),
            per_page=validate_limit(per_page, max_val=200),
        )
        return _dump(format_page(data, format_label))
    except Exception as exc:
        return _error("list_labels", exc)


@mcp.tool()
def get_label(label_id: str) -> str:
    """Fetch a label by UUID."""
    try:
        label_id = validate_uuid(label_id, "label_id")
        return _dump(format_label(_get_client().get_label(label_id)))
    except Exception as exc:
        return _error("get_label", exc)


@mcp.tool()
def create_label(name: str, color: str = "") -> str:
    """Create a label. `color` is a CSS hex string like '#3f51b5'."""
    try:
        name = validate_non_empty(name, "name")
        body: dict[str, Any] = {"name": name}
        if color:
            body["color"] = color
        return _dump(format_label(_get_client().create_label(body)))
    except Exception as exc:
        return _error("create_label", exc)


@mcp.tool()
def update_label(label_id: str, name: str = "", color: str = "") -> str:
    """Patch a label."""
    try:
        label_id = validate_uuid(label_id, "label_id")
        patch: dict[str, Any] = {}
        if name:
            patch["name"] = name
        if color:
            patch["color"] = color
        if not patch:
            raise ValueError("update_label called with no changes.")
        return _dump(format_label(_get_client().update_label(label_id, patch)))
    except Exception as exc:
        return _error("update_label", exc)


@mcp.tool()
def delete_label(label_id: str) -> str:
    """Delete a label by UUID."""
    try:
        label_id = validate_uuid(label_id, "label_id")
        _get_client().delete_label(label_id)
        return _dump({"deleted": label_id})
    except Exception as exc:
        return _error("delete_label", exc)
