"""Client wrapper for the Mealie REST API."""

from typing import Any, NoReturn

import httpx

from .auth import get_credentials


class MealieError(Exception):
    """User-facing Mealie API error."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class MealieClient:
    """Validated, formatted interface to the Mealie REST API."""

    def __init__(self) -> None:
        creds = get_credentials()
        self._base_url = creds["base_url"]
        self._token = creds["token"]
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=30.0,
            headers={"Authorization": f"Bearer {self._token}"},
        )

    def _raise(self, resp: httpx.Response, action: str) -> NoReturn:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise MealieError(
            f"{action} failed ({resp.status_code}): {detail}",
            status_code=resp.status_code,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        action: str = "request",
    ) -> Any:
        resp = self._http.request(method, path, params=params, json=json)
        if resp.status_code >= 400:
            self._raise(resp, action)
        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except Exception:
            return resp.text

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def about(self) -> dict[str, Any]:
        """Get version/health info. Does not require auth on the server side."""
        return self._request("GET", "/api/app/about", action="about")

    def whoami(self) -> dict[str, Any]:
        """Return the current user — useful for verifying the token works."""
        return self._request("GET", "/api/users/self", action="whoami")

    # ------------------------------------------------------------------
    # Recipes
    # ------------------------------------------------------------------

    def list_recipes(
        self,
        *,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
        order_by: str | None = None,
        order_direction: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "perPage": per_page}
        if search:
            params["search"] = search
        if order_by:
            params["orderBy"] = order_by
        if order_direction:
            params["orderDirection"] = order_direction
        return self._request(
            "GET", "/api/recipes", params=params, action="list_recipes"
        )

    def get_recipe(self, slug: str) -> dict[str, Any]:
        return self._request(
            "GET", f"/api/recipes/{slug}", action=f"get_recipe({slug})"
        )

    def create_recipe(self, name: str) -> str:
        """Create an empty recipe. Returns the new slug."""
        result = self._request(
            "POST", "/api/recipes", json={"name": name}, action="create_recipe"
        )
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and "slug" in result:
            return result["slug"]
        raise MealieError(f"Unexpected create_recipe response: {result!r}")

    def create_recipe_from_url(
        self, url: str, *, include_tags: bool = False
    ) -> str:
        """Scrape a recipe from a URL. Returns the new slug."""
        result = self._request(
            "POST",
            "/api/recipes/create-url",
            json={"url": url, "includeTags": include_tags},
            action="create_recipe_from_url",
        )
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and "slug" in result:
            return result["slug"]
        raise MealieError(f"Unexpected create-url response: {result!r}")

    def update_recipe(self, slug: str, patch: dict[str, Any]) -> dict[str, Any]:
        """Patch a recipe with the given fields. Returns the updated recipe."""
        if not patch:
            raise MealieError("update_recipe called with no fields to update.")
        return self._request(
            "PATCH",
            f"/api/recipes/{slug}",
            json=patch,
            action=f"update_recipe({slug})",
        )

    def delete_recipe(self, slug: str) -> dict[str, Any] | None:
        return self._request(
            "DELETE", f"/api/recipes/{slug}", action=f"delete_recipe({slug})"
        )
