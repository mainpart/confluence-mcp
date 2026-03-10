# confluence-mcp

MCP server for Confluence REST API. 4 read-only tools. Bearer token (PAT) auth.

API documentation:
- [REST API v1](https://developer.atlassian.com/cloud/confluence/rest/v1/)
- [REST API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/)

## Setup

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `CONFLUENCE_URL` | yes | REST API base URL, e.g. `https://wiki.example.com/rest/api` |
| `CONFLUENCE_TOKEN` | yes | Personal Access Token |
| `CONFLUENCE_VERIFY_SSL` | no | `true` (default) / `false` |
| `MCP_TRANSPORT` | no | `stdio` (default), `sse`, `streamable-http` |
| `MCP_HOST` / `MCP_PORT` | no | For sse/streamable-http (default `0.0.0.0:8000`) |

### Claude Desktop

`~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "confluence": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/mainpart/confluence-mcp", "confluence-mcp"],
      "env": {
        "CONFLUENCE_URL": "https://wiki.example.com/rest/api",
        "CONFLUENCE_TOKEN": "your-pat-token"
      }
    }
  }
}
```

### Claude Code

`.claude/settings.json`:

```json
{
  "mcpServers": {
    "confluence": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/mainpart/confluence-mcp", "confluence-mcp"],
      "env": {
        "CONFLUENCE_URL": "https://wiki.example.com/rest/api",
        "CONFLUENCE_TOKEN": "your-pat-token"
      }
    }
  }
}
```

## Tools (4)

| Tool | Description |
|---|---|
| `get_content_by_id` | Get content by ID with optional expand and status |
| `download_attachment` | Download attachment by content ID and attachment ID |
| `get_spaces` | List/filter spaces by key, type, status, label |
| `search_content` | Search content by text query, optionally filter by space and type |

## License

MIT
