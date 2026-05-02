# mcp-mealie

MCP server for Mealie

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

## Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mealie": {
      "command": "uvx",
      "args": ["mcp-mealie"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add mealie -- uvx mcp-mealie
```

## Tools

<!-- Add your MCP tools here -->

## Development

```bash
uv sync
uv run pytest tests/ -x -q
uv run ruff check src/ tests/
uv run pyright src/
```
