"""Response formatters for Mealie data."""

from collections.abc import Callable
from typing import Any

# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------


def format_page(
    data: dict[str, Any],
    item_formatter: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Format a paginated list response using the given per-item formatter."""
    return {
        "page": data.get("page"),
        "per_page": data.get("per_page"),
        "total": data.get("total"),
        "total_pages": data.get("total_pages"),
        "items": [item_formatter(i) for i in (data.get("items") or [])],
    }


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


def format_about(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": data.get("version"),
        "production": data.get("production"),
        "demo_status": data.get("demoStatus"),
        "default_group_slug": data.get("defaultGroupSlug"),
        "allow_signup": data.get("allowSignup"),
        "enable_oidc": data.get("enableOidc"),
    }


def format_user(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": data.get("id"),
        "username": data.get("username"),
        "full_name": data.get("fullName"),
        "email": data.get("email"),
        "admin": data.get("admin"),
        "group": data.get("group"),
        "household": data.get("household"),
    }


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


def format_recipe_summary(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r.get("id"),
        "slug": r.get("slug"),
        "name": r.get("name"),
        "description": r.get("description"),
        "recipe_yield": r.get("recipeYield"),
        "total_time": r.get("totalTime"),
        "rating": r.get("rating"),
        "tags": [t.get("name") for t in (r.get("tags") or []) if t.get("name")],
        "categories": [
            c.get("name") for c in (r.get("recipeCategory") or []) if c.get("name")
        ],
    }


def format_recipe_full(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r.get("id"),
        "slug": r.get("slug"),
        "name": r.get("name"),
        "description": r.get("description"),
        "recipe_yield": r.get("recipeYield"),
        "prep_time": r.get("prepTime"),
        "perform_time": r.get("performTime"),
        "total_time": r.get("totalTime"),
        "rating": r.get("rating"),
        "org_url": r.get("orgURL"),
        "ingredients": [
            i.get("display") or i.get("note") or ""
            for i in (r.get("recipeIngredient") or [])
        ],
        "instructions": [
            s.get("text", "") for s in (r.get("recipeInstructions") or [])
        ],
        "tags": [t.get("name") for t in (r.get("tags") or []) if t.get("name")],
        "categories": [
            c.get("name") for c in (r.get("recipeCategory") or []) if c.get("name")
        ],
        "tools": [t.get("name") for t in (r.get("tools") or []) if t.get("name")],
        "notes": [
            {"title": n.get("title"), "text": n.get("text")}
            for n in (r.get("notes") or [])
        ],
    }


def format_recipe_page(data: dict[str, Any]) -> dict[str, Any]:
    return format_page(data, format_recipe_summary)


# ---------------------------------------------------------------------------
# Cookbooks
# ---------------------------------------------------------------------------


def format_cookbook(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "slug": c.get("slug"),
        "description": c.get("description"),
        "position": c.get("position"),
        "public": c.get("public"),
        "query_filter_string": c.get("queryFilterString"),
    }


# ---------------------------------------------------------------------------
# Meal plans
# ---------------------------------------------------------------------------


def format_mealplan(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": m.get("id"),
        "date": m.get("date"),
        "entry_type": m.get("entryType"),
        "title": m.get("title"),
        "text": m.get("text"),
        "recipe_id": m.get("recipeId"),
        "recipe": (format_recipe_summary(m["recipe"]) if m.get("recipe") else None),
    }


def format_mealplan_rule(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r.get("id"),
        "day": r.get("day"),
        "entry_type": r.get("entryType"),
        "query_filter_string": r.get("queryFilterString"),
    }


# ---------------------------------------------------------------------------
# Shopping
# ---------------------------------------------------------------------------


def format_shopping_list(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": s.get("id"),
        "name": s.get("name"),
        "group_id": s.get("groupId"),
        "household_id": s.get("householdId"),
        "list_items": [format_shopping_item(i) for i in (s.get("listItems") or [])],
        "recipe_references": [
            {"recipe_id": r.get("recipeId"), "scale": r.get("recipeQuantity")}
            for r in (s.get("recipeReferences") or [])
        ],
    }


def format_recipe_attach(list_id: str, recipe_id: str, response: Any) -> dict[str, Any]:
    """Slim down the bulk add-recipe-to-list response.

    Mealie returns the full updated list (every item, every household label
    setting). For LLM consumption we only need: which list, which recipe,
    and the items that were just added by this attach.
    """
    out: dict[str, Any] = {"list_id": list_id, "recipe_id": recipe_id}
    if not isinstance(response, dict):
        out["items_added"] = 0
        return out
    items = response.get("listItems") or []
    new_items = [
        format_shopping_item(i)
        for i in items
        if any(
            r.get("recipeId") == recipe_id for r in (i.get("recipeReferences") or [])
        )
    ]
    out["items_added"] = len(new_items)
    out["items"] = new_items
    return out


def format_shopping_item(i: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": i.get("id"),
        "shopping_list_id": i.get("shoppingListId"),
        "note": i.get("note"),
        "quantity": i.get("quantity"),
        "checked": i.get("checked"),
        "is_food": i.get("isFood"),
        "food_id": i.get("foodId"),
        "unit_id": i.get("unitId"),
        "label_id": i.get("labelId"),
        "position": i.get("position"),
        "display": i.get("display"),
    }


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


def format_taxonomy_item(t: dict[str, Any]) -> dict[str, Any]:
    """Shared formatter for categories / tags / tools (same shape)."""
    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "slug": t.get("slug"),
        "on_hand": t.get("onHand"),
    }


def format_food(f: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f.get("id"),
        "name": f.get("name"),
        "plural_name": f.get("pluralName"),
        "description": f.get("description"),
        "label": (
            {"id": f["label"].get("id"), "name": f["label"].get("name")}
            if f.get("label")
            else None
        ),
    }


def format_unit(u: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": u.get("id"),
        "name": u.get("name"),
        "plural_name": u.get("pluralName"),
        "abbreviation": u.get("abbreviation"),
        "plural_abbreviation": u.get("pluralAbbreviation"),
        "description": u.get("description"),
        "fraction": u.get("fraction"),
        "use_abbreviation": u.get("useAbbreviation"),
    }


def format_label(label: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": label.get("id"),
        "name": label.get("name"),
        "color": label.get("color"),
        "group_id": label.get("groupId"),
    }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def format_parsed_ingredient(p: dict[str, Any]) -> dict[str, Any]:
    """Format a single parsed-ingredient response."""
    ing = p.get("ingredient", {})
    return {
        "input": p.get("input"),
        "confidence": p.get("confidence"),
        "ingredient": {
            "quantity": ing.get("quantity"),
            "unit": (ing.get("unit") or {}).get("name") if ing.get("unit") else None,
            "food": (ing.get("food") or {}).get("name") if ing.get("food") else None,
            "note": ing.get("note"),
            "display": ing.get("display"),
        },
    }
