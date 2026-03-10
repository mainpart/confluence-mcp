# confluence-mcp

MCP server for Confluence REST API. 5 read-only tools. Bearer token (PAT) auth.

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

### Claude Desktop / Claude Code — uvx (no install)

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

### pip install

```bash
pip install git+https://github.com/mainpart/confluence-mcp
```

Then configure the MCP client:

```json
{
  "mcpServers": {
    "confluence": {
      "command": "confluence-mcp",
      "env": {
        "CONFLUENCE_URL": "https://wiki.example.com/rest/api",
        "CONFLUENCE_TOKEN": "your-pat-token"
      }
    }
  }
}
```

Or run directly:

```bash
export CONFLUENCE_URL="https://wiki.example.com/rest/api"
export CONFLUENCE_TOKEN="your-pat-token"
confluence-mcp
```

### Run from source

```bash
git clone https://github.com/mainpart/confluence-mcp
cd confluence-mcp
pip install -e .
confluence-mcp
```

Or without installing:

```bash
python -m confluence_mcp.server
```

## Tools (5)

| Tool | Description |
|---|---|
| `get_content_by_id` | Page with body (storage format), ancestors, child pages, attachments |
| `download_attachment` | Download attachment by content ID and attachment ID |
| `get_spaces` | List spaces (key + name), filter by type, status, label |
| `get_comments` | Page comments (footer + inline with markerRef and originalSelection) |
| `search` | Full-text search with filters: title, space, type, creator, contributor, label, ancestor, parent, dates |

## License

MIT
