# mcp-mealie

MCP server for [Mealie](https://mealie.io/) — exposes a Mealie instance's REST
API to MCP clients (Claude Desktop, Claude Code, etc.) so an LLM can read,
search, scrape, edit, and delete recipes (and meal plans, shopping lists,
cookbooks, taxonomy) on your behalf.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- A reachable Mealie instance (self-hosted or otherwise)
- A Mealie API token: in Mealie, click your avatar → **Profile** → **API Tokens**
  → **Generate**. The token inherits the issuing user's permissions, so for
  automation prefer a dedicated non-admin user.

## Setup

```bash
uv sync
```

## Configuration

Two environment variables are required:

| Variable             | Purpose                                            |
| -------------------- | -------------------------------------------------- |
| `MEALIE_BASE_URL`    | Root URL of your Mealie instance, no trailing path |
| `MEALIE_API_TOKEN`   | Long-lived bearer token from Profile → API Tokens  |

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mealie": {
      "command": "uvx",
      "args": ["mcp-mealie"],
      "env": {
        "MEALIE_BASE_URL": "https://mealie.example.com",
        "MEALIE_API_TOKEN": "eyJhbGc..."
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add mealie \
  -e MEALIE_BASE_URL=https://mealie.example.com \
  -e MEALIE_API_TOKEN=eyJhbGc... \
  -- uvx mcp-mealie
```

## Tools

### Diagnostics
| Tool         | Description                            |
| ------------ | -------------------------------------- |
| `get_about`  | Server version / health (no auth path) |
| `whoami`     | Confirm the token works                |

### Recipes (full CRUD + scrape + rating + content)
| Tool                              | Description                                                           |
| --------------------------------- | --------------------------------------------------------------------- |
| `list_recipes`                    | Paginated list with search and ordering                               |
| `get_recipe`                      | Full recipe by slug                                                   |
| `create_recipe`                   | Empty recipe by name                                                  |
| `create_recipe_from_url`          | Scrape from a URL                                                     |
| `update_recipe`                   | Patch common metadata fields                                          |
| `set_recipe_ingredients`          | Replace ingredient list (raw text, no food/unit binding)              |
| `set_recipe_ingredients_parsed`   | Replace ingredient list, parsing each line and binding food/unit IDs  |
| `parse_recipe_ingredients`        | Re-parse the recipe's existing free-text ingredients in place         |
| `set_recipe_instructions`         | Replace step list (JSON array of lines)                               |
| `set_recipe_notes`                | Replace notes (JSON array of {title,text})                            |
| `set_recipe_rating`               | Per-user rating / favorite                                            |
| `delete_recipe`                   | Delete by slug                                                        |

### Cookbooks (full CRUD)
| Tool                | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `list_cookbooks`    | Saved recipe filters                                 |
| `get_cookbook`      | By UUID                                              |
| `create_cookbook`   | name, description, query_filter_string, public       |
| `update_cookbook`   | Patch                                                |
| `delete_cookbook`   | Delete                                               |

### Meal plans (full CRUD)
| Tool                | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `list_mealplans`    | Range-filtered list                                  |
| `get_mealplan`      | By id                                                |
| `create_mealplan`   | date + entry_type, plus recipe_id or title/text      |
| `update_mealplan`   | Patch                                                |
| `delete_mealplan`   | Delete                                               |

### Meal-plan rules (full CRUD)
Used by Mealie's random-meal generator.

| Tool                       | Description                                   |
| -------------------------- | --------------------------------------------- |
| `list_mealplan_rules`      | List rules                                    |
| `get_mealplan_rule`        | By UUID                                       |
| `create_mealplan_rule`     | day, entry_type, query_filter_string          |
| `update_mealplan_rule`     | Patch                                         |
| `delete_mealplan_rule`     | Delete                                        |

### Shopping lists (CRUD + recipe attach)
| Tool                                  | Description                              |
| ------------------------------------- | ---------------------------------------- |
| `list_shopping_lists`                 |                                          |
| `get_shopping_list`                   | Includes items                           |
| `create_shopping_list`                |                                          |
| `update_shopping_list`                | Rename                                   |
| `delete_shopping_list`                |                                          |
| `add_recipe_to_shopping_list`         | Add a recipe's ingredients (with scale)  |
| `remove_recipe_from_shopping_list`    | Reverse the above                        |

### Shopping items (full CRUD)
| Tool                            | Description                                |
| ------------------------------- | ------------------------------------------ |
| `list_shopping_items`           | Optionally filter by `list_id`             |
| `get_shopping_item`             |                                            |
| `create_shopping_item`          | Free-form note or structured (food/unit)   |
| `create_shopping_items_bulk`    | JSON-array bulk create                     |
| `update_shopping_item`          | Includes check/uncheck                     |
| `delete_shopping_item`          |                                            |

### Parser
| Tool                        | Description                                       |
| --------------------------- | ------------------------------------------------- |
| `parse_ingredient`          | One string → quantity/unit/food                   |
| `parse_ingredients`         | JSON array of strings → list of parsed results    |

### Taxonomy (full CRUD per resource)

Categories, tags, and kitchen tools share a uniform `{name}` create surface.

| Resource    | Tools                                                                  |
| ----------- | ---------------------------------------------------------------------- |
| Categories  | `list_categories`, `get_category`, `create_category`, `update_category`, `delete_category` |
| Tags        | `list_tags`, `get_tag`, `create_tag`, `update_tag`, `delete_tag`       |
| Kitchen tools | `list_tools`, `get_tool`, `create_tool`, `update_tool`, `delete_tool` |
| Foods       | `list_foods`, `get_food`, `create_food`, `update_food`, `delete_food`  |
| Units       | `list_units`, `get_unit`, `create_unit`, `update_unit`, `delete_unit`  |
| Labels      | `list_labels`, `get_label`, `create_label`, `update_label`, `delete_label` |

## Development

```bash
uv sync
uv run pytest tests/ -x -q
uv run ruff check src/ tests/
uv run pyright src/
```
