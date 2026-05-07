"""MCP server with Mealie tools.

Tool return-type conventions:
- Data tools return real `dict` or `list[dict]` so FastMCP serializes them as
  proper structured content (no json.dumps wrapping).
- Errors are raised as exceptions; FastMCP translates them into MCP error
  responses with `isError=true`.
"""

import json
import re
import uuid
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import MealieClient
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


# Matches "Header: rest" where the header is a single line, has no internal
# colons or periods, and is short. Used to auto-split step text into the
# step's `summary` field (rendered as a per-step header in Mealie's UI).
# `title` is reserved for section dividers that group multiple steps and
# is left empty unless the caller passes the dict form with a title.
_STEP_HEADER_RE = re.compile(r"^([^:.\n]{1,60}):\s+(.+)$", re.DOTALL)


def _build_recipe_step(item: Any) -> dict[str, Any]:
    """Coerce a string or {title, summary, text} dict into a RecipeStep payload.

    Strings starting with "Header: rest" are auto-split: the header goes
    into `summary` (per-step header) and the rest into `text`. `title`
    is left empty so Mealie won't render a section break before the step.

    Pass the dict form for explicit control:
      - title: section divider rendered above the step
      - summary: per-step header rendered inside the step card
      - text: the step body (required)
    """
    if isinstance(item, str):
        match = _STEP_HEADER_RE.match(item)
        summary = match.group(1).strip() if match else ""
        text = match.group(2).strip() if match else item
        title = ""
    elif isinstance(item, dict) and "text" in item:
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        text = str(item["text"])
    else:
        raise ValueError(
            "each step must be a string or an object with at least 'text'."
        )
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "summary": summary,
        "text": text,
        "ingredientReferences": [],
    }


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@mcp.tool()
def get_about() -> dict:
    """Return Mealie server version and basic info. Confirms connectivity."""
    return format_about(_get_client().about())


@mcp.tool()
def whoami() -> dict:
    """Return the user owning the configured API token. Confirms auth works."""
    return format_user(_get_client().whoami())


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
) -> dict:
    """List recipes with optional search, sorting, and pagination."""
    data = _get_client().list_recipes(
        search=search or None,
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=100),
        order_by=order_by or None,
        order_direction=order_direction or None,
    )
    return format_recipe_page(data)


@mcp.tool()
def get_recipe(slug: str) -> dict:
    """Fetch a full recipe by slug, including ingredients and instructions."""
    slug = validate_slug(slug)
    return format_recipe_full(_get_client().get_recipe(slug))


@mcp.tool()
def create_recipe(name: str) -> dict:
    """Create an empty recipe by name. Returns the new slug."""
    name = validate_non_empty(name, "name")
    slug = _get_client().create_recipe(name)
    return {"slug": slug, "name": name}


@mcp.tool()
def create_recipe_from_url(url: str, include_tags: bool = False) -> dict:
    """Scrape a recipe from a URL using Mealie's scraper. Returns the new slug."""
    url = validate_url(url)
    slug = _get_client().create_recipe_from_url(url, include_tags=include_tags)
    return {"slug": slug, "source_url": url}


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
) -> dict:
    """Patch a recipe. Only non-empty fields are sent.

    Note: rating is per-user in Mealie 2.x+ and is not exposed here. Set it
    via the Mealie UI (or a future dedicated tool) against
    POST /api/users/{user_id}/ratings/{slug}.
    """
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
    return format_recipe_full(_get_client().update_recipe(slug, patch))


@mcp.tool()
def delete_recipe(slug: str) -> dict:
    """Delete a recipe by slug. This is permanent."""
    slug = validate_slug(slug)
    _get_client().delete_recipe(slug)
    return {"deleted": slug}


@mcp.tool()
def set_recipe_rating(
    slug: str,
    rating: float = -1.0,
    is_favorite: int = -1,
) -> dict:
    """Set the calling user's rating and/or favorite flag for a recipe.

    rating: 0-5 (decimals allowed). Pass -1 to leave unchanged.
    is_favorite: 0=remove, 1=add. Pass -1 to leave unchanged.
    """
    slug = validate_slug(slug)
    rating_val: float | None = rating if rating >= 0 else None
    favorite_val: bool | None = bool(is_favorite) if is_favorite in (0, 1) else None
    if rating_val is None and favorite_val is None:
        raise ValueError("set_recipe_rating called with nothing to change.")
    _get_client().set_recipe_rating(slug, rating=rating_val, is_favorite=favorite_val)
    return {"slug": slug, "rating": rating_val, "is_favorite": favorite_val}


@mcp.tool()
def set_recipe_ingredients(slug: str, ingredients_json: str) -> dict:
    """Replace a recipe's ingredient list with the given lines.

    `ingredients_json` is a JSON array of strings, one per ingredient
    (e.g. `["1 cup flour", "2 eggs"]`). Each string is stored verbatim;
    the user can re-parse to structured quantity/unit/food in the
    Mealie UI afterward to enable shopping-list integration.
    """
    slug = validate_slug(slug)
    items = json.loads(ingredients_json)
    if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
        raise ValueError("ingredients_json must be a JSON array of strings.")
    if not items:
        raise ValueError("ingredients_json cannot be empty.")
    recipe_ingredient = [{"note": s, "display": s, "originalText": s} for s in items]
    return format_recipe_full(
        _get_client().update_recipe(slug, {"recipeIngredient": recipe_ingredient})
    )


@mcp.tool()
def set_recipe_instructions(slug: str, instructions_json: str) -> dict:
    """Replace a recipe's instruction steps with the given lines.

    `instructions_json` is a JSON array. Each element is either:
      - a string ("Boil water: bring 4 quarts to a rolling boil"), or
      - an object ({"title": "Prep", "summary": "Boil water", "text": "..."})

    Strings starting with a short "Header: rest" prefix are auto-split:
    the header goes into the step's `summary` (rendered as a per-step
    header in Mealie's UI), and the rest goes into `text`. The `title`
    field is reserved for section dividers between groups of steps and
    is only set when the dict form provides one.
    """
    slug = validate_slug(slug)
    raw = json.loads(instructions_json)
    if not isinstance(raw, list):
        raise ValueError("instructions_json must be a JSON array.")
    if not raw:
        raise ValueError("instructions_json cannot be empty.")
    recipe_instructions = [_build_recipe_step(item) for item in raw]
    return format_recipe_full(
        _get_client().update_recipe(slug, {"recipeInstructions": recipe_instructions})
    )


@mcp.tool()
def set_recipe_notes(slug: str, notes_json: str) -> dict:
    """Replace a recipe's notes with the given JSON array.

    `notes_json` is a JSON array of `{title, text}` objects. `title`
    is optional; `text` is required. Example:
    `[{"title": "Tip", "text": "Toast the spices first."}]`.
    """
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
    return format_recipe_full(_get_client().update_recipe(slug, {"notes": notes}))


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
def parse_recipe_ingredients(slug: str, min_confidence: float = 0.5) -> dict:
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
    slug = validate_slug(slug)
    client = _get_client()
    recipe = client.get_recipe(slug)
    raw_lines: list[str] = []
    for ing in recipe.get("recipeIngredient") or []:
        text = ing.get("originalText") or ing.get("display") or ing.get("note") or ""
        if text:
            raw_lines.append(text)
    if not raw_lines:
        raise ValueError("Recipe has no ingredient lines to parse.")
    bound, summary = _parse_and_bind(client, raw_lines, min_confidence=min_confidence)
    client.update_recipe(slug, {"recipeIngredient": bound})
    return {"slug": slug, "ingredients": summary}


@mcp.tool()
def set_recipe_ingredients_parsed(
    slug: str, ingredients_json: str, min_confidence: float = 0.5
) -> dict:
    """Like set_recipe_ingredients, but parses each line and binds food/unit IDs.

    `ingredients_json` is a JSON array of strings. Each is run through
    Mealie's NLP parser; recognized food / unit names are matched
    against the existing taxonomy (or created if not present), so the
    resulting recipe is shopping-list-aggregation-ready.

    Lines whose parsed average confidence falls below `min_confidence`
    are stored as free text.

    Returns a per-line summary of what was bound vs. left as free text.
    """
    slug = validate_slug(slug)
    items = json.loads(ingredients_json)
    if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
        raise ValueError("ingredients_json must be a JSON array of strings.")
    if not items:
        raise ValueError("ingredients_json cannot be empty.")
    client = _get_client()
    bound, summary = _parse_and_bind(client, items, min_confidence=min_confidence)
    client.update_recipe(slug, {"recipeIngredient": bound})
    return {"slug": slug, "ingredients": summary}


# ---------------------------------------------------------------------------
# Cookbooks
# ---------------------------------------------------------------------------


@mcp.tool()
def list_cookbooks(page: int = 1, per_page: int = 50) -> dict:
    """List cookbooks (saved recipe filters) for the current household."""
    data = _get_client().list_cookbooks(
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=100),
    )
    return format_page(data, format_cookbook)


@mcp.tool()
def get_cookbook(cookbook_id: str) -> dict:
    """Fetch a cookbook by UUID."""
    cookbook_id = validate_uuid(cookbook_id, "cookbook_id")
    return format_cookbook(_get_client().get_cookbook(cookbook_id))


@mcp.tool()
def create_cookbook(
    name: str,
    description: str = "",
    query_filter_string: str = "",
    public: bool = False,
) -> dict:
    """Create a cookbook. `query_filter_string` is the Mealie filter DSL."""
    name = validate_non_empty(name, "name")
    body: dict[str, Any] = {"name": name, "public": public}
    if description:
        body["description"] = description
    if query_filter_string:
        body["queryFilterString"] = query_filter_string
    return format_cookbook(_get_client().create_cookbook(body))


@mcp.tool()
def update_cookbook(
    cookbook_id: str,
    name: str = "",
    description: str = "",
    query_filter_string: str = "",
    public: int = -1,
) -> dict:
    """Patch a cookbook. Use public=1 to make public, public=0 to unpublish."""
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
    return format_cookbook(_get_client().update_cookbook(cookbook_id, patch))


@mcp.tool()
def delete_cookbook(cookbook_id: str) -> dict:
    """Delete a cookbook by UUID."""
    cookbook_id = validate_uuid(cookbook_id, "cookbook_id")
    _get_client().delete_cookbook(cookbook_id)
    return {"deleted": cookbook_id}


# ---------------------------------------------------------------------------
# Meal plans
# ---------------------------------------------------------------------------


@mcp.tool()
def list_mealplans(
    start_date: str = "",
    end_date: str = "",
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """List meal-plan entries, optionally bounded by start_date/end_date."""
    sd = validate_iso_date(start_date) if start_date else None
    ed = validate_iso_date(end_date) if end_date else None
    data = _get_client().list_mealplans(
        start_date=sd,
        end_date=ed,
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=200),
    )
    return format_page(data, format_mealplan)


@mcp.tool()
def get_mealplan(mealplan_id: int) -> dict:
    """Fetch a meal-plan entry by numeric id."""
    return format_mealplan(_get_client().get_mealplan(mealplan_id))


@mcp.tool()
def create_mealplan(
    date: str,
    entry_type: str = "dinner",
    title: str = "",
    text: str = "",
    recipe_id: str = "",
) -> dict:
    """Create a meal-plan entry.

    Supply either `recipe_id` (UUID) for a recipe entry, or `title`/`text`
    for a freeform entry. `entry_type` is one of: breakfast, lunch, dinner, side.
    """
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
    return format_mealplan(_get_client().create_mealplan(body))


@mcp.tool()
def update_mealplan(
    mealplan_id: int,
    date: str = "",
    entry_type: str = "",
    title: str = "",
    text: str = "",
    recipe_id: str = "",
) -> dict:
    """Patch a meal-plan entry. Only non-empty fields are sent."""
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
    return format_mealplan(_get_client().update_mealplan(mealplan_id, patch))


@mcp.tool()
def delete_mealplan(mealplan_id: int) -> dict:
    """Delete a meal-plan entry by id."""
    _get_client().delete_mealplan(mealplan_id)
    return {"deleted": mealplan_id}


# ---------------------------------------------------------------------------
# Meal plan rules
# ---------------------------------------------------------------------------


@mcp.tool()
def list_mealplan_rules(page: int = 1, per_page: int = 50) -> dict:
    """List meal-plan rules used by the random-meal generator."""
    data = _get_client().list_mealplan_rules(
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=100),
    )
    return format_page(data, format_mealplan_rule)


@mcp.tool()
def get_mealplan_rule(rule_id: str) -> dict:
    """Fetch a meal-plan rule by UUID."""
    rule_id = validate_uuid(rule_id, "rule_id")
    return format_mealplan_rule(_get_client().get_mealplan_rule(rule_id))


@mcp.tool()
def create_mealplan_rule(
    day: str = "unset",
    entry_type: str = "dinner",
    query_filter_string: str = "",
) -> dict:
    """Create a meal-plan rule.

    `day` is monday..sunday or "unset" (any day).
    `entry_type` is breakfast/lunch/dinner/side.
    `query_filter_string` is the Mealie filter DSL (e.g. `tags.name = "quick"`).
    """
    body = {
        "day": validate_day_of_week(day),
        "entryType": validate_entry_type(entry_type),
        "queryFilterString": query_filter_string,
    }
    return format_mealplan_rule(_get_client().create_mealplan_rule(body))


@mcp.tool()
def update_mealplan_rule(
    rule_id: str,
    day: str = "",
    entry_type: str = "",
    query_filter_string: str = "",
) -> dict:
    """Patch a meal-plan rule."""
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
    return format_mealplan_rule(_get_client().update_mealplan_rule(rule_id, patch))


@mcp.tool()
def delete_mealplan_rule(rule_id: str) -> dict:
    """Delete a meal-plan rule by UUID."""
    rule_id = validate_uuid(rule_id, "rule_id")
    _get_client().delete_mealplan_rule(rule_id)
    return {"deleted": rule_id}


# ---------------------------------------------------------------------------
# Shopping lists
# ---------------------------------------------------------------------------


@mcp.tool()
def list_shopping_lists(page: int = 1, per_page: int = 50) -> dict:
    """List shopping lists for the current household."""
    data = _get_client().list_shopping_lists(
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=100),
    )
    return format_page(data, format_shopping_list)


@mcp.tool()
def get_shopping_list(list_id: str) -> dict:
    """Fetch a shopping list by UUID, including its items."""
    list_id = validate_uuid(list_id, "list_id")
    return format_shopping_list(_get_client().get_shopping_list(list_id))


@mcp.tool()
def create_shopping_list(name: str) -> dict:
    """Create a shopping list with the given name."""
    name = validate_non_empty(name, "name")
    return format_shopping_list(_get_client().create_shopping_list({"name": name}))


@mcp.tool()
def update_shopping_list(list_id: str, name: str = "") -> dict:
    """Patch a shopping list. Currently supports renaming."""
    list_id = validate_uuid(list_id, "list_id")
    patch: dict[str, Any] = {}
    if name:
        patch["name"] = name
    if not patch:
        raise ValueError("update_shopping_list called with no changes.")
    return format_shopping_list(_get_client().update_shopping_list(list_id, patch))


@mcp.tool()
def delete_shopping_list(list_id: str) -> dict:
    """Delete a shopping list by UUID."""
    list_id = validate_uuid(list_id, "list_id")
    _get_client().delete_shopping_list(list_id)
    return {"deleted": list_id}


@mcp.tool()
def add_recipe_to_shopping_list(list_id: str, recipe_id: str, scale: int = 1) -> dict:
    """Add a recipe's ingredients to a shopping list. `scale` multiplies amounts."""
    list_id = validate_uuid(list_id, "list_id")
    recipe_id = validate_uuid(recipe_id, "recipe_id")
    result = _get_client().add_recipe_to_shopping_list(
        list_id, recipe_id, scale=scale if scale != 1 else None
    )
    return format_recipe_attach(list_id, recipe_id, result)


@mcp.tool()
def remove_recipe_from_shopping_list(list_id: str, recipe_id: str) -> dict:
    """Remove a recipe's ingredients from a shopping list."""
    list_id = validate_uuid(list_id, "list_id")
    recipe_id = validate_uuid(recipe_id, "recipe_id")
    _get_client().remove_recipe_from_shopping_list(list_id, recipe_id)
    return {"list_id": list_id, "recipe_id": recipe_id, "removed": True}


# ---------------------------------------------------------------------------
# Shopping items
# ---------------------------------------------------------------------------


@mcp.tool()
def list_shopping_items(list_id: str = "", page: int = 1, per_page: int = 100) -> dict:
    """List shopping items, optionally filtered to one shopping list."""
    lid = validate_uuid(list_id, "list_id") if list_id else None
    data = _get_client().list_shopping_items(
        list_id=lid,
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=200),
    )
    return format_page(data, format_shopping_item)


@mcp.tool()
def get_shopping_item(item_id: str) -> dict:
    """Fetch a shopping item by UUID."""
    item_id = validate_uuid(item_id, "item_id")
    return format_shopping_item(_get_client().get_shopping_item(item_id))


@mcp.tool()
def create_shopping_item(
    list_id: str,
    note: str = "",
    quantity: float = 0.0,
    is_food: bool = False,
    food_id: str = "",
    unit_id: str = "",
    label_id: str = "",
) -> dict | list:
    """Create a single shopping item on a list.

    Free-form items: pass `note` (e.g. "carrots, 2 lb").
    Structured items: set is_food=true and pass `food_id`, optional `unit_id`.
    """
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
            return format_shopping_item(created[0])
        return [format_shopping_item(i) for i in created]
    if isinstance(result, list):
        return [format_shopping_item(i) for i in result]
    return format_shopping_item(result)


@mcp.tool()
def create_shopping_items_bulk(items_json: str) -> dict | list:
    """Bulk-create shopping items from a JSON array.

    `items_json` is a JSON array of item objects. Each item must include
    `shoppingListId` (UUID); `note` and `quantity` are typical optional fields.
    """
    items = json.loads(items_json)
    if not isinstance(items, list) or not items:
        raise ValueError("items_json must be a non-empty JSON array.")
    result = _get_client().create_shopping_items_bulk(items)
    if isinstance(result, dict) and "createdItems" in result:
        created = result.get("createdItems") or []
        return [format_shopping_item(i) for i in created]
    if isinstance(result, list):
        return [format_shopping_item(i) for i in result]
    return result


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
) -> dict:
    """Patch a shopping item. checked: 0=unchecked, 1=checked, -1=leave."""
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
    return format_shopping_item(_get_client().update_shopping_item(item_id, patch))


@mcp.tool()
def delete_shopping_item(item_id: str) -> dict:
    """Delete a shopping item by UUID."""
    item_id = validate_uuid(item_id, "item_id")
    _get_client().delete_shopping_item(item_id)
    return {"deleted": item_id}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


@mcp.tool()
def parse_ingredient(text: str, parser: str = "nlp") -> dict:
    """Parse a single ingredient string into structured quantity/unit/food.

    `parser` is "nlp" (default, CRF model) or "brute" (regex fallback).
    """
    text = validate_non_empty(text, "text")
    parser = validate_parser(parser)
    return format_parsed_ingredient(_get_client().parse_ingredient(text, parser=parser))


@mcp.tool()
def parse_ingredients(ingredients_json: str, parser: str = "nlp") -> list[dict]:
    """Parse many ingredient strings. `ingredients_json` is a JSON string array."""
    items = json.loads(ingredients_json)
    if not isinstance(items, list) or not all(isinstance(s, str) for s in items):
        raise ValueError("ingredients_json must be a JSON array of strings.")
    if not items:
        raise ValueError("ingredients_json cannot be empty.")
    parser = validate_parser(parser)
    result = _get_client().parse_ingredients(items, parser=parser)
    return [format_parsed_ingredient(p) for p in result]


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@mcp.tool()
def list_categories(page: int = 1, per_page: int = 100) -> dict:
    """List recipe categories."""
    data = _get_client().list_categories(
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=200),
    )
    return format_page(data, format_taxonomy_item)


@mcp.tool()
def get_category(category_id: str) -> dict:
    """Fetch a category by UUID."""
    category_id = validate_uuid(category_id, "category_id")
    return format_taxonomy_item(_get_client().get_category(category_id))


@mcp.tool()
def create_category(name: str) -> dict:
    """Create a category."""
    name = validate_non_empty(name, "name")
    return format_taxonomy_item(_get_client().create_category({"name": name}))


@mcp.tool()
def update_category(category_id: str, name: str) -> dict:
    """Rename a category by UUID."""
    category_id = validate_uuid(category_id, "category_id")
    name = validate_non_empty(name, "name")
    return format_taxonomy_item(
        _get_client().update_category(category_id, {"name": name})
    )


@mcp.tool()
def delete_category(category_id: str) -> dict:
    """Delete a category by UUID."""
    category_id = validate_uuid(category_id, "category_id")
    _get_client().delete_category(category_id)
    return {"deleted": category_id}


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tags(page: int = 1, per_page: int = 100) -> dict:
    """List recipe tags."""
    data = _get_client().list_tags(
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=200),
    )
    return format_page(data, format_taxonomy_item)


@mcp.tool()
def get_tag(tag_id: str) -> dict:
    """Fetch a tag by UUID."""
    tag_id = validate_uuid(tag_id, "tag_id")
    return format_taxonomy_item(_get_client().get_tag(tag_id))


@mcp.tool()
def create_tag(name: str) -> dict:
    """Create a tag."""
    name = validate_non_empty(name, "name")
    return format_taxonomy_item(_get_client().create_tag({"name": name}))


@mcp.tool()
def update_tag(tag_id: str, name: str) -> dict:
    """Rename a tag by UUID."""
    tag_id = validate_uuid(tag_id, "tag_id")
    name = validate_non_empty(name, "name")
    return format_taxonomy_item(_get_client().update_tag(tag_id, {"name": name}))


@mcp.tool()
def delete_tag(tag_id: str) -> dict:
    """Delete a tag by UUID."""
    tag_id = validate_uuid(tag_id, "tag_id")
    _get_client().delete_tag(tag_id)
    return {"deleted": tag_id}


# ---------------------------------------------------------------------------
# Tools (kitchen tools)
# ---------------------------------------------------------------------------


@mcp.tool()
def list_tools(page: int = 1, per_page: int = 100) -> dict:
    """List kitchen tools."""
    data = _get_client().list_tools(
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=200),
    )
    return format_page(data, format_taxonomy_item)


@mcp.tool()
def get_tool(tool_id: str) -> dict:
    """Fetch a kitchen tool by UUID."""
    tool_id = validate_uuid(tool_id, "tool_id")
    return format_taxonomy_item(_get_client().get_tool(tool_id))


@mcp.tool()
def create_tool(name: str) -> dict:
    """Create a kitchen tool."""
    name = validate_non_empty(name, "name")
    return format_taxonomy_item(_get_client().create_tool({"name": name}))


@mcp.tool()
def update_tool(tool_id: str, name: str) -> dict:
    """Rename a kitchen tool by UUID."""
    tool_id = validate_uuid(tool_id, "tool_id")
    name = validate_non_empty(name, "name")
    return format_taxonomy_item(_get_client().update_tool(tool_id, {"name": name}))


@mcp.tool()
def delete_tool(tool_id: str) -> dict:
    """Delete a kitchen tool by UUID."""
    tool_id = validate_uuid(tool_id, "tool_id")
    _get_client().delete_tool(tool_id)
    return {"deleted": tool_id}


# ---------------------------------------------------------------------------
# Foods
# ---------------------------------------------------------------------------


@mcp.tool()
def list_foods(page: int = 1, per_page: int = 100) -> dict:
    """List ingredient foods."""
    data = _get_client().list_foods(
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=200),
    )
    return format_page(data, format_food)


@mcp.tool()
def get_food(food_id: str) -> dict:
    """Fetch a food by UUID."""
    food_id = validate_uuid(food_id, "food_id")
    return format_food(_get_client().get_food(food_id))


@mcp.tool()
def create_food(
    name: str,
    plural_name: str = "",
    description: str = "",
    label_id: str = "",
) -> dict:
    """Create a food (ingredient)."""
    name = validate_non_empty(name, "name")
    body: dict[str, Any] = {"name": name}
    if plural_name:
        body["pluralName"] = plural_name
    if description:
        body["description"] = description
    if label_id:
        body["labelId"] = validate_uuid(label_id, "label_id")
    return format_food(_get_client().create_food(body))


@mcp.tool()
def update_food(
    food_id: str,
    name: str = "",
    plural_name: str = "",
    description: str = "",
    label_id: str = "",
) -> dict:
    """Patch a food."""
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
    return format_food(_get_client().update_food(food_id, patch))


@mcp.tool()
def delete_food(food_id: str) -> dict:
    """Delete a food by UUID."""
    food_id = validate_uuid(food_id, "food_id")
    _get_client().delete_food(food_id)
    return {"deleted": food_id}


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


@mcp.tool()
def list_units(page: int = 1, per_page: int = 100) -> dict:
    """List units of measure."""
    data = _get_client().list_units(
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=200),
    )
    return format_page(data, format_unit)


@mcp.tool()
def get_unit(unit_id: str) -> dict:
    """Fetch a unit by UUID."""
    unit_id = validate_uuid(unit_id, "unit_id")
    return format_unit(_get_client().get_unit(unit_id))


@mcp.tool()
def create_unit(
    name: str,
    plural_name: str = "",
    abbreviation: str = "",
    plural_abbreviation: str = "",
    description: str = "",
    fraction: int = -1,
    use_abbreviation: int = -1,
) -> dict:
    """Create a unit of measure. fraction/use_abbreviation: 0=false, 1=true."""
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
    return format_unit(_get_client().create_unit(body))


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
) -> dict:
    """Patch a unit."""
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
    return format_unit(_get_client().update_unit(unit_id, patch))


@mcp.tool()
def delete_unit(unit_id: str) -> dict:
    """Delete a unit by UUID."""
    unit_id = validate_uuid(unit_id, "unit_id")
    _get_client().delete_unit(unit_id)
    return {"deleted": unit_id}


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


@mcp.tool()
def list_labels(page: int = 1, per_page: int = 100) -> dict:
    """List multi-purpose labels (used by foods, shopping items, etc.)."""
    data = _get_client().list_labels(
        page=validate_page(page),
        per_page=validate_limit(per_page, max_val=200),
    )
    return format_page(data, format_label)


@mcp.tool()
def get_label(label_id: str) -> dict:
    """Fetch a label by UUID."""
    label_id = validate_uuid(label_id, "label_id")
    return format_label(_get_client().get_label(label_id))


@mcp.tool()
def create_label(name: str, color: str = "") -> dict:
    """Create a label. `color` is a CSS hex string like '#3f51b5'."""
    name = validate_non_empty(name, "name")
    body: dict[str, Any] = {"name": name}
    if color:
        body["color"] = color
    return format_label(_get_client().create_label(body))


@mcp.tool()
def update_label(label_id: str, name: str = "", color: str = "") -> dict:
    """Patch a label."""
    label_id = validate_uuid(label_id, "label_id")
    patch: dict[str, Any] = {}
    if name:
        patch["name"] = name
    if color:
        patch["color"] = color
    if not patch:
        raise ValueError("update_label called with no changes.")
    return format_label(_get_client().update_label(label_id, patch))


@mcp.tool()
def delete_label(label_id: str) -> dict:
    """Delete a label by UUID."""
    label_id = validate_uuid(label_id, "label_id")
    _get_client().delete_label(label_id)
    return {"deleted": label_id}
