# Confluence MCP Server

MCP server that wraps Confluence REST API v1 and exposes tools for LLM agents.
Single file: `src/confluence_mcp/server.py`. Auth: Bearer token (PAT).

## Project structure

```
src/confluence_mcp/server.py   — all MCP tools and ConfluenceClient
api/confluence-openapi-v1.json — Confluence REST API v1 OpenAPI spec
api/confluence-openapi-v2.json — Confluence REST API v2 OpenAPI spec
pyproject.toml                 — package config, dependencies: httpx, fastmcp
```

## Current tools

- `get_content_by_id(id)` — page with body, ancestors, child pages, attachments
- `download_attachment(id, attachment_id)` — download attachment content
- `get_spaces()` — list spaces (key + name)
- `search(query | cql)` — text search or raw CQL

## Adding new tools

1. Find the endpoint in `api/confluence-openapi-v1.json` or `api/confluence-openapi-v2.json`
2. Add a `@mcp.tool()` async function in `server.py`
3. Use `conf.request(method, path, params=..., json_data=...)` for API calls
4. **Always post-process the response** — see "Output optimization" below

### Tool template

```python
@mcp.tool()
async def my_tool(param: str) -> str:
    """Short description for LLM. Include parameter semantics."""
    raw = json.loads(await conf.request("GET", f"/some/endpoint/{param}"))
    result = {
        "field1": raw.get("field1"),
        "field2": raw.get("nested", {}).get("field2"),
    }
    return json.dumps(result, ensure_ascii=False)
```

## Output optimization

Confluence API returns ~60-70% noise per response. Every tool MUST strip it.

### What to remove

- `_expandable` — empty stubs everywhere, zero value
- `_links` — `webui`, `self`, `edit`, `tinyui`, `collection`, `base`, `context` (all derivable from id/key)
- `profilePicture`, `userKey`, `username` in user objects — keep only `displayName`
- `extensions.position` — useless
- `metadata.mediaType` — duplicates `extensions.mediaType` in attachments
- `type` when always the same (e.g. "page", "attachment", "global")
- `status` when always "current"
- Pagination `_links` — replace with `hasMore: bool`

### What to keep

- Identifiers: `id`, `key` (spaces), `title`
- Content: `body.storage.value` (compact Confluence Storage Format HTML)
- Version: `version.number`, `version.when`, `version.by.displayName`
- Relationships: `ancestors[].{id,title}`, `childPages[].{id,title}`
- Attachments: `id`, `title`, `mediaType`, `fileSize`, `download` link
- Pagination: `start`, `size`, `totalSize`, `hasMore`

### Why body.storage (not body.view)

- `body.storage` (~10KB) — compact XML with `<ac:*>` macros, PlantUML source
- `body.view` (~10KB) — rendered HTML, macros expanded, readable but larger
- `body.styled_view` (~80KB) — full HTML page with embedded CSS, never use
- `body.view` embeds base64 `data-diagramdata` blobs (~1.2KB each) for draw.io — pure noise for LLM
- `body.storage` keeps draw.io as a small `<ac:structured-macro>` tag (~200 bytes)

### Attachment patterns

draw.io diagrams create 2-3 files per diagram:
- `.mxfile` — source XML (useful for LLM to understand diagram)
- `.png` — rendered preview (binary, not useful for LLM)
- `.mxfile.backup` — backup (ignore)

## CQL (Confluence Query Language)

Used by the `search` tool. Key fields:
- `text`, `title` — content search (use `~` operator)
- `space` — space key (use `=`)
- `type` — page, blogpost, comment, attachment
- `creator`, `contributor` — username
- `label` — page labels
- `ancestor`, `parent` — page hierarchy by ID
- `created`, `lastModified` — dates (use `>=`, `<=`)
- `mention` — user mentioned on page

Operators: `=`, `!=`, `~` (contains), `>`, `<`, `>=`, `<=`, `IN`, `NOT IN`

## Environment variables

- `CONFLUENCE_URL` — base API URL (e.g. `https://confluence.example.com/rest/api`)
- `CONFLUENCE_TOKEN` — Personal Access Token (Bearer auth)
- `CONFLUENCE_VERIFY_SSL` — set to `false` for self-signed certs
