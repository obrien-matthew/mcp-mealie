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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

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

    @staticmethod
    def _page_params(page: int, per_page: int) -> dict[str, Any]:
        return {"page": page, "perPage": per_page}

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def about(self) -> dict[str, Any]:
        return self._request("GET", "/api/app/about", action="about")

    def whoami(self) -> dict[str, Any]:
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
        params: dict[str, Any] = self._page_params(page, per_page)
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

    # ------------------------------------------------------------------
    # Cookbooks
    # ------------------------------------------------------------------

    def list_cookbooks(self, *, page: int = 1, per_page: int = 50) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/households/cookbooks",
            params=self._page_params(page, per_page),
            action="list_cookbooks",
        )

    def get_cookbook(self, cookbook_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/households/cookbooks/{cookbook_id}",
            action=f"get_cookbook({cookbook_id})",
        )

    def create_cookbook(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/households/cookbooks",
            json=body,
            action="create_cookbook",
        )

    def update_cookbook(
        self, cookbook_id: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        if not patch:
            raise MealieError("update_cookbook called with no fields to update.")
        return self._request(
            "PATCH",
            f"/api/households/cookbooks/{cookbook_id}",
            json=patch,
            action=f"update_cookbook({cookbook_id})",
        )

    def delete_cookbook(self, cookbook_id: str) -> Any:
        return self._request(
            "DELETE",
            f"/api/households/cookbooks/{cookbook_id}",
            action=f"delete_cookbook({cookbook_id})",
        )

    # ------------------------------------------------------------------
    # Meal plans
    # ------------------------------------------------------------------

    def list_mealplans(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        params: dict[str, Any] = self._page_params(page, per_page)
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._request(
            "GET",
            "/api/households/mealplans",
            params=params,
            action="list_mealplans",
        )

    def get_mealplan(self, mealplan_id: int) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/households/mealplans/{mealplan_id}",
            action=f"get_mealplan({mealplan_id})",
        )

    def create_mealplan(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/households/mealplans",
            json=body,
            action="create_mealplan",
        )

    def update_mealplan(
        self, mealplan_id: int, patch: dict[str, Any]
    ) -> dict[str, Any]:
        if not patch:
            raise MealieError("update_mealplan called with no fields to update.")
        return self._request(
            "PATCH",
            f"/api/households/mealplans/{mealplan_id}",
            json=patch,
            action=f"update_mealplan({mealplan_id})",
        )

    def delete_mealplan(self, mealplan_id: int) -> Any:
        return self._request(
            "DELETE",
            f"/api/households/mealplans/{mealplan_id}",
            action=f"delete_mealplan({mealplan_id})",
        )

    # ------------------------------------------------------------------
    # Meal plan rules
    # ------------------------------------------------------------------

    def list_mealplan_rules(
        self, *, page: int = 1, per_page: int = 50
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/households/mealplans/rules",
            params=self._page_params(page, per_page),
            action="list_mealplan_rules",
        )

    def get_mealplan_rule(self, rule_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/households/mealplans/rules/{rule_id}",
            action=f"get_mealplan_rule({rule_id})",
        )

    def create_mealplan_rule(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/households/mealplans/rules",
            json=body,
            action="create_mealplan_rule",
        )

    def update_mealplan_rule(
        self, rule_id: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        if not patch:
            raise MealieError("update_mealplan_rule called with no fields to update.")
        return self._request(
            "PATCH",
            f"/api/households/mealplans/rules/{rule_id}",
            json=patch,
            action=f"update_mealplan_rule({rule_id})",
        )

    def delete_mealplan_rule(self, rule_id: str) -> Any:
        return self._request(
            "DELETE",
            f"/api/households/mealplans/rules/{rule_id}",
            action=f"delete_mealplan_rule({rule_id})",
        )

    # ------------------------------------------------------------------
    # Shopping lists
    # ------------------------------------------------------------------

    def list_shopping_lists(
        self, *, page: int = 1, per_page: int = 50
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/households/shopping/lists",
            params=self._page_params(page, per_page),
            action="list_shopping_lists",
        )

    def get_shopping_list(self, list_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/households/shopping/lists/{list_id}",
            action=f"get_shopping_list({list_id})",
        )

    def create_shopping_list(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/households/shopping/lists",
            json=body,
            action="create_shopping_list",
        )

    def update_shopping_list(
        self, list_id: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        if not patch:
            raise MealieError("update_shopping_list called with no fields to update.")
        return self._request(
            "PATCH",
            f"/api/households/shopping/lists/{list_id}",
            json=patch,
            action=f"update_shopping_list({list_id})",
        )

    def delete_shopping_list(self, list_id: str) -> Any:
        return self._request(
            "DELETE",
            f"/api/households/shopping/lists/{list_id}",
            action=f"delete_shopping_list({list_id})",
        )

    def add_recipe_to_shopping_list(
        self, list_id: str, recipe_id: str, *, scale: int | None = None
    ) -> Any:
        body: dict[str, Any] | None = None
        if scale is not None:
            body = {"recipeIncrementQuantity": scale}
        return self._request(
            "POST",
            f"/api/households/shopping/lists/{list_id}/recipe/{recipe_id}",
            json=body,
            action=f"add_recipe_to_shopping_list({list_id},{recipe_id})",
        )

    def remove_recipe_from_shopping_list(
        self, list_id: str, recipe_id: str
    ) -> Any:
        return self._request(
            "DELETE",
            f"/api/households/shopping/lists/{list_id}/recipe/{recipe_id}",
            action=f"remove_recipe_from_shopping_list({list_id},{recipe_id})",
        )

    # ------------------------------------------------------------------
    # Shopping items
    # ------------------------------------------------------------------

    def list_shopping_items(
        self,
        *,
        list_id: str | None = None,
        page: int = 1,
        per_page: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = self._page_params(page, per_page)
        if list_id:
            params["queryFilter"] = f"shoppingListId={list_id}"
        return self._request(
            "GET",
            "/api/households/shopping/items",
            params=params,
            action="list_shopping_items",
        )

    def get_shopping_item(self, item_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/households/shopping/items/{item_id}",
            action=f"get_shopping_item({item_id})",
        )

    def create_shopping_item(self, body: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/api/households/shopping/items",
            json=body,
            action="create_shopping_item",
        )

    def create_shopping_items_bulk(self, items: list[dict[str, Any]]) -> Any:
        return self._request(
            "POST",
            "/api/households/shopping/items/create-bulk",
            json=items,
            action="create_shopping_items_bulk",
        )

    def update_shopping_item(
        self, item_id: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        if not patch:
            raise MealieError("update_shopping_item called with no fields to update.")
        return self._request(
            "PATCH",
            f"/api/households/shopping/items/{item_id}",
            json=patch,
            action=f"update_shopping_item({item_id})",
        )

    def delete_shopping_item(self, item_id: str) -> Any:
        return self._request(
            "DELETE",
            f"/api/households/shopping/items/{item_id}",
            action=f"delete_shopping_item({item_id})",
        )

    # ------------------------------------------------------------------
    # Parser
    # ------------------------------------------------------------------

    def parse_ingredient(self, text: str, *, parser: str = "nlp") -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/parser/ingredient",
            json={"ingredient": text, "parser": parser},
            action="parse_ingredient",
        )

    def parse_ingredients(
        self, ingredients: list[str], *, parser: str = "nlp"
    ) -> list[dict[str, Any]]:
        return self._request(
            "POST",
            "/api/parser/ingredients",
            json={"ingredients": ingredients, "parser": parser},
            action="parse_ingredients",
        )

    def parse_recipe_ingredients(
        self, slug: str, *, parser: str = "nlp"
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/recipes/{slug}/ingredients/parse-ingredients",
            json={"parser": parser},
            action=f"parse_recipe_ingredients({slug})",
        )

    # ------------------------------------------------------------------
    # Generic taxonomy CRUD (categories / tags / tools)
    # ------------------------------------------------------------------

    def _taxonomy_list(
        self, path: str, page: int, per_page: int, action: str
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            path,
            params=self._page_params(page, per_page),
            action=action,
        )

    def _taxonomy_get(self, path: str, item_id: str, action: str) -> dict[str, Any]:
        return self._request("GET", f"{path}/{item_id}", action=action)

    def _taxonomy_create(
        self, path: str, body: dict[str, Any], action: str
    ) -> dict[str, Any]:
        return self._request("POST", path, json=body, action=action)

    def _taxonomy_update(
        self, path: str, item_id: str, patch: dict[str, Any], action: str
    ) -> dict[str, Any]:
        if not patch:
            raise MealieError(f"{action} called with no fields to update.")
        return self._request(
            "PATCH", f"{path}/{item_id}", json=patch, action=action
        )

    def _taxonomy_delete(self, path: str, item_id: str, action: str) -> Any:
        return self._request("DELETE", f"{path}/{item_id}", action=action)

    # Categories
    def list_categories(self, *, page: int = 1, per_page: int = 100):
        return self._taxonomy_list(
            "/api/categories", page, per_page, "list_categories"
        )

    def get_category(self, category_id: str):
        return self._taxonomy_get(
            "/api/categories", category_id, f"get_category({category_id})"
        )

    def create_category(self, body: dict[str, Any]):
        return self._taxonomy_create("/api/categories", body, "create_category")

    def update_category(self, category_id: str, patch: dict[str, Any]):
        return self._taxonomy_update(
            "/api/categories",
            category_id,
            patch,
            f"update_category({category_id})",
        )

    def delete_category(self, category_id: str):
        return self._taxonomy_delete(
            "/api/categories", category_id, f"delete_category({category_id})"
        )

    # Tags
    def list_tags(self, *, page: int = 1, per_page: int = 100):
        return self._taxonomy_list("/api/tags", page, per_page, "list_tags")

    def get_tag(self, tag_id: str):
        return self._taxonomy_get("/api/tags", tag_id, f"get_tag({tag_id})")

    def create_tag(self, body: dict[str, Any]):
        return self._taxonomy_create("/api/tags", body, "create_tag")

    def update_tag(self, tag_id: str, patch: dict[str, Any]):
        return self._taxonomy_update(
            "/api/tags", tag_id, patch, f"update_tag({tag_id})"
        )

    def delete_tag(self, tag_id: str):
        return self._taxonomy_delete("/api/tags", tag_id, f"delete_tag({tag_id})")

    # Tools
    def list_tools(self, *, page: int = 1, per_page: int = 100):
        return self._taxonomy_list("/api/tools", page, per_page, "list_tools")

    def get_tool(self, tool_id: str):
        return self._taxonomy_get("/api/tools", tool_id, f"get_tool({tool_id})")

    def create_tool(self, body: dict[str, Any]):
        return self._taxonomy_create("/api/tools", body, "create_tool")

    def update_tool(self, tool_id: str, patch: dict[str, Any]):
        return self._taxonomy_update(
            "/api/tools", tool_id, patch, f"update_tool({tool_id})"
        )

    def delete_tool(self, tool_id: str):
        return self._taxonomy_delete(
            "/api/tools", tool_id, f"delete_tool({tool_id})"
        )

    # Foods
    def list_foods(self, *, page: int = 1, per_page: int = 100):
        return self._taxonomy_list("/api/foods", page, per_page, "list_foods")

    def get_food(self, food_id: str):
        return self._taxonomy_get("/api/foods", food_id, f"get_food({food_id})")

    def create_food(self, body: dict[str, Any]):
        return self._taxonomy_create("/api/foods", body, "create_food")

    def update_food(self, food_id: str, patch: dict[str, Any]):
        return self._taxonomy_update(
            "/api/foods", food_id, patch, f"update_food({food_id})"
        )

    def delete_food(self, food_id: str):
        return self._taxonomy_delete(
            "/api/foods", food_id, f"delete_food({food_id})"
        )

    # Units
    def list_units(self, *, page: int = 1, per_page: int = 100):
        return self._taxonomy_list("/api/units", page, per_page, "list_units")

    def get_unit(self, unit_id: str):
        return self._taxonomy_get("/api/units", unit_id, f"get_unit({unit_id})")

    def create_unit(self, body: dict[str, Any]):
        return self._taxonomy_create("/api/units", body, "create_unit")

    def update_unit(self, unit_id: str, patch: dict[str, Any]):
        return self._taxonomy_update(
            "/api/units", unit_id, patch, f"update_unit({unit_id})"
        )

    def delete_unit(self, unit_id: str):
        return self._taxonomy_delete(
            "/api/units", unit_id, f"delete_unit({unit_id})"
        )

    # Labels
    def list_labels(self, *, page: int = 1, per_page: int = 100):
        return self._taxonomy_list(
            "/api/groups/labels", page, per_page, "list_labels"
        )

    def get_label(self, label_id: str):
        return self._taxonomy_get(
            "/api/groups/labels", label_id, f"get_label({label_id})"
        )

    def create_label(self, body: dict[str, Any]):
        return self._taxonomy_create(
            "/api/groups/labels", body, "create_label"
        )

    def update_label(self, label_id: str, patch: dict[str, Any]):
        return self._taxonomy_update(
            "/api/groups/labels",
            label_id,
            patch,
            f"update_label({label_id})",
        )

    def delete_label(self, label_id: str):
        return self._taxonomy_delete(
            "/api/groups/labels", label_id, f"delete_label({label_id})"
        )
