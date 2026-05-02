"""Response formatters for Mealie data."""

from typing import Any


def format_about(data: dict[str, Any]) -> dict[str, Any]:
    """Format the /api/app/about response."""
    return {
        "version": data.get("version"),
        "production": data.get("production"),
        "demo_status": data.get("demoStatus"),
        "default_group_slug": data.get("defaultGroupSlug"),
        "allow_signup": data.get("allowSignup"),
        "enable_oidc": data.get("enableOidc"),
    }


def format_user(data: dict[str, Any]) -> dict[str, Any]:
    """Format /api/users/self into the fields useful for a token check."""
    return {
        "id": data.get("id"),
        "username": data.get("username"),
        "full_name": data.get("fullName"),
        "email": data.get("email"),
        "admin": data.get("admin"),
        "group": data.get("group"),
        "household": data.get("household"),
    }


def format_recipe_summary(r: dict[str, Any]) -> dict[str, Any]:
    """Format a recipe list-row into a compact LLM-friendly summary."""
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
    """Format a full recipe response, flattening nested ingredient/step shapes."""
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
    """Format a paginated recipe list response."""
    return {
        "page": data.get("page"),
        "per_page": data.get("per_page"),
        "total": data.get("total"),
        "total_pages": data.get("total_pages"),
        "items": [format_recipe_summary(r) for r in (data.get("items") or [])],
    }
