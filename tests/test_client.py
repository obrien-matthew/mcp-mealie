"""Tests for the Mealie client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from mealie_mcp.client import MealieClient, MealieError

_MOCK_REQUEST = httpx.Request("GET", "http://test")


def _json_response(data, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data, request=_MOCK_REQUEST)


def _text_response(text: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=text, request=_MOCK_REQUEST)


@pytest.fixture
def client():
    with patch("mealie_mcp.client.get_credentials") as mock_creds:
        mock_creds.return_value = {
            "base_url": "https://mealie.test",
            "token": "tok",
        }
        with patch.object(httpx.Client, "__init__", return_value=None):
            c = MealieClient()
    c._http = MagicMock(spec=httpx.Client)
    return c


class TestAbout:
    def test_returns_json(self, client):
        client._http.request.return_value = _json_response({"version": "v2"})
        assert client.about() == {"version": "v2"}
        client._http.request.assert_called_once_with(
            "GET", "/api/app/about", params=None, json=None
        )


class TestWhoami:
    def test_returns_user(self, client):
        client._http.request.return_value = _json_response({"username": "me"})
        assert client.whoami()["username"] == "me"


class TestListRecipes:
    def test_passes_params(self, client):
        client._http.request.return_value = _json_response({"items": []})
        client.list_recipes(search="taco", page=2, per_page=10)
        _, kwargs = client._http.request.call_args
        assert kwargs["params"] == {"page": 2, "perPage": 10, "search": "taco"}

    def test_omits_optional(self, client):
        client._http.request.return_value = _json_response({"items": []})
        client.list_recipes()
        _, kwargs = client._http.request.call_args
        assert kwargs["params"] == {"page": 1, "perPage": 20}


class TestGetRecipe:
    def test_path(self, client):
        client._http.request.return_value = _json_response({"slug": "tacos"})
        client.get_recipe("tacos")
        args, _ = client._http.request.call_args
        assert args == ("GET", "/api/recipes/tacos")


class TestCreateRecipe:
    def test_returns_slug_from_string(self, client):
        client._http.request.return_value = _text_response('"tacos"')
        # POST returns a JSON string, which httpx will decode as str
        client._http.request.return_value = httpx.Response(
            201, json="tacos", request=_MOCK_REQUEST
        )
        assert client.create_recipe("Tacos") == "tacos"

    def test_returns_slug_from_dict(self, client):
        client._http.request.return_value = _json_response({"slug": "tacos"})
        assert client.create_recipe("Tacos") == "tacos"


class TestCreateRecipeFromUrl:
    def test_posts_url(self, client):
        client._http.request.return_value = httpx.Response(
            201, json="tacos", request=_MOCK_REQUEST
        )
        slug = client.create_recipe_from_url("https://example.com/r", include_tags=True)
        assert slug == "tacos"
        _, kwargs = client._http.request.call_args
        assert kwargs["json"] == {
            "url": "https://example.com/r",
            "includeTags": True,
        }


class TestUpdateRecipe:
    def test_sends_patch(self, client):
        client._http.request.return_value = _json_response({"slug": "tacos"})
        client.update_recipe("tacos", {"name": "Better Tacos"})
        args, kwargs = client._http.request.call_args
        assert args == ("PATCH", "/api/recipes/tacos")
        assert kwargs["json"] == {"name": "Better Tacos"}

    def test_rejects_empty_patch(self, client):
        with pytest.raises(MealieError, match="no fields"):
            client.update_recipe("tacos", {})


class TestDeleteRecipe:
    def test_path(self, client):
        client._http.request.return_value = httpx.Response(
            204, request=_MOCK_REQUEST
        )
        assert client.delete_recipe("tacos") is None
        args, _ = client._http.request.call_args
        assert args == ("DELETE", "/api/recipes/tacos")


class TestCookbooks:
    def test_list_path(self, client):
        client._http.request.return_value = _json_response({"items": []})
        client.list_cookbooks()
        args, kwargs = client._http.request.call_args
        assert args == ("GET", "/api/households/cookbooks")
        assert kwargs["params"] == {"page": 1, "perPage": 50}

    def test_create_body(self, client):
        client._http.request.return_value = _json_response({"id": "u"})
        client.create_cookbook({"name": "Quick"})
        _, kwargs = client._http.request.call_args
        assert kwargs["json"] == {"name": "Quick"}


class TestMealplans:
    def test_list_with_dates(self, client):
        client._http.request.return_value = _json_response({"items": []})
        client.list_mealplans(start_date="2026-05-01", end_date="2026-05-07")
        _, kwargs = client._http.request.call_args
        assert kwargs["params"]["start_date"] == "2026-05-01"
        assert kwargs["params"]["end_date"] == "2026-05-07"

    def test_create_path(self, client):
        client._http.request.return_value = _json_response({"id": 1})
        client.create_mealplan({"date": "2026-05-02", "entryType": "dinner"})
        args, _ = client._http.request.call_args
        assert args == ("POST", "/api/households/mealplans")


class TestShopping:
    def test_add_recipe(self, client):
        client._http.request.return_value = _json_response([])
        client.add_recipe_to_shopping_list("L", "R", scale=2)
        args, kwargs = client._http.request.call_args
        assert args == ("POST", "/api/households/shopping/lists/L/recipe/R")
        assert kwargs["json"] == {"recipeIncrementQuantity": 2}

    def test_add_recipe_no_scale(self, client):
        client._http.request.return_value = _json_response([])
        client.add_recipe_to_shopping_list("L", "R")
        _, kwargs = client._http.request.call_args
        assert kwargs["json"] is None

    def test_list_items_filter(self, client):
        client._http.request.return_value = _json_response({"items": []})
        client.list_shopping_items(list_id="L1")
        _, kwargs = client._http.request.call_args
        assert kwargs["params"]["queryFilter"] == "shoppingListId=L1"


class TestParser:
    def test_single(self, client):
        client._http.request.return_value = _json_response({"input": "1 c flour"})
        client.parse_ingredient("1 c flour", parser="brute")
        args, kwargs = client._http.request.call_args
        assert args == ("POST", "/api/parser/ingredient")
        assert kwargs["json"] == {"ingredient": "1 c flour", "parser": "brute"}

    def test_bulk(self, client):
        client._http.request.return_value = _json_response([])
        client.parse_ingredients(["a", "b"])
        _, kwargs = client._http.request.call_args
        assert kwargs["json"] == {"ingredients": ["a", "b"], "parser": "nlp"}


class TestTaxonomy:
    def test_categories_path(self, client):
        client._http.request.return_value = _json_response({"items": []})
        client.list_categories()
        args, _ = client._http.request.call_args
        assert args == ("GET", "/api/categories")

    def test_labels_path(self, client):
        client._http.request.return_value = _json_response({"items": []})
        client.list_labels()
        args, _ = client._http.request.call_args
        assert args == ("GET", "/api/groups/labels")

    def test_food_patch(self, client):
        client._http.request.return_value = _json_response({"id": "f"})
        client.update_food("f", {"name": "carrot"})
        args, kwargs = client._http.request.call_args
        assert args == ("PATCH", "/api/foods/f")
        assert kwargs["json"] == {"name": "carrot"}


class TestErrorHandling:
    def test_raises_on_4xx(self, client):
        client._http.request.return_value = _json_response(
            {"detail": "not found"}, status=404
        )
        with pytest.raises(MealieError) as exc:
            client.get_recipe("missing")
        assert exc.value.status_code == 404
        assert "not found" in exc.value.message

    def test_handles_text_error_body(self, client):
        client._http.request.return_value = _text_response("server boom", status=500)
        with pytest.raises(MealieError) as exc:
            client.about()
        assert exc.value.status_code == 500
