# confluence-mcp

MCP server for Confluence REST API. 7 read-only tools. Bearer token (PAT) auth.

API documentation:
- [REST API v1](https://developer.atlassian.com/cloud/confluence/rest/v1/)
- [REST API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/)

## Setup

```bash
# install
uv pip install -e .

# or run directly
uv run confluence-mcp
```

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
      "command": "uv",
      "args": ["run", "--directory", "/path/to/confluence-mcp", "confluence-mcp"],
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
      "command": "uv",
      "args": ["run", "--directory", "/path/to/confluence-mcp", "confluence-mcp"],
      "env": {
        "CONFLUENCE_URL": "https://wiki.example.com/rest/api",
        "CONFLUENCE_TOKEN": "your-pat-token"
      }
    }
  }
}
```

## Tools (4)

| Tool | Method | Path | Description |
|---|---|---|---|
| `getContentById` | GET | `/content/{id}` | Read a page by ID |
| `downloadAttachment` | GET | `/content/{id}/child/attachment/{attachmentId}/download` | Download attachment |
| `getSpaces` | GET | `/space` | List spaces |
| `searchContentByCQL` | GET | `/content/search` | Search content by CQL |

## License

MIT
