# confluence-mcp

MCP server for Confluence REST API. Bearer token (PAT) auth.

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

### Creating a Personal Access Token (PAT)

```bash
curl -s -u 'your-username:your-password' \
  -X POST -H "Content-Type: application/json" \
  -d '{"name":"my-mcp-token"}' \
  "https://wiki.example.com/rest/pat/latest/tokens"
# Save rawToken from the response — it won't be shown again
```

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
