# mcp-mealie

MCP server for [Mealie](https://mealie.io/) — exposes a Mealie instance's REST
API to MCP clients (Claude Desktop, Claude Code, etc.) so an LLM can read,
search, scrape, edit, and delete recipes on your behalf.

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

| Tool         | Description                                      |
| ------------ | ------------------------------------------------ |
| `get_about`  | Mealie version / health (no auth required)       |
| `whoami`     | Current user — confirms the token works          |

### Recipes (full CRUD)

| Tool                      | Description                                           |
| ------------------------- | ----------------------------------------------------- |
| `list_recipes`            | Paginated list with optional search and ordering      |
| `get_recipe`              | Full recipe by slug (ingredients, steps, tags, etc.)  |
| `create_recipe`           | Create an empty recipe by name; returns the new slug  |
| `create_recipe_from_url`  | Scrape a recipe from a URL via Mealie's scraper       |
| `update_recipe`           | Patch common fields (name, description, times, etc.)  |
| `delete_recipe`           | Delete a recipe by slug (permanent)                   |

## Development

```bash
uv sync
uv run pytest tests/ -x -q
uv run ruff check src/ tests/
uv run pyright src/
```
