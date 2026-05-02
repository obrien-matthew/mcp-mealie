"""MCP server with Mealie tools for recipe management."""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import MealieClient, MealieError
from .formatting import (
    format_about,
    format_recipe_full,
    format_recipe_page,
    format_user,
)
from .validation import (
    validate_limit,
    validate_non_empty,
    validate_page,
    validate_slug,
    validate_url,
)

mcp = FastMCP("mcp-mealie")

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
    """List recipes with optional search and pagination.

    Args:
        search: Optional substring search across recipe names.
        page: 1-indexed page number.
        per_page: Items per page (1-100).
        order_by: Optional sort field (e.g. "name", "created_at", "rating").
        order_direction: Optional "asc" or "desc".
    """
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
    """Create an empty recipe with the given name. Returns the new slug.

    For scraping a recipe from a website, use `create_recipe_from_url`.
    To populate fields after creation, use `update_recipe` with the slug.
    """
    try:
        name = validate_non_empty(name, "name")
        slug = _get_client().create_recipe(name)
        return _dump({"slug": slug, "name": name})
    except Exception as exc:
        return _error("create_recipe", exc)


@mcp.tool()
def create_recipe_from_url(url: str, include_tags: bool = False) -> str:
    """Scrape a recipe from a URL using Mealie's built-in scraper.

    Args:
        url: A recipe webpage URL.
        include_tags: If true, attempt to import keyword tags from the page.

    Returns the new recipe's slug.
    """
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
    rating: int = -1,
    org_url: str = "",
) -> str:
    """Patch a recipe. Only non-empty / non-default fields are sent.

    Args:
        slug: The recipe's slug (immutable identifier).
        name: New display name.
        description: New description / blurb.
        recipe_yield: e.g. "4 servings".
        prep_time: Free-form duration string, e.g. "PT15M" or "15 minutes".
        perform_time: Cook/active time.
        total_time: Total time.
        rating: 0-5 (use -1 to leave unchanged).
        org_url: Source URL for the recipe.
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
        if rating >= 0:
            patch["rating"] = rating
        if org_url:
            patch["orgURL"] = validate_url(org_url)
        if not patch:
            raise ValueError(
                "update_recipe called with no changes. "
                "Provide at least one field to update."
            )
        result = _get_client().update_recipe(slug, patch)
        return _dump(format_recipe_full(result))
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
