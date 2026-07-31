# Confluence MCP Server

MCP server that wraps Confluence REST API v1 and exposes tools for LLM agents.
Single file: `src/confluence_mcp/server.py`. Auth: Bearer token (PAT).

## Project structure

```
src/confluence_mcp/server.py   — all MCP tools and ConfluenceClient
api/confluence-openapi-v1.json — Confluence REST API v1 OpenAPI spec
api/confluence-openapi-v2.json — Confluence REST API v2 OpenAPI spec
```

## Current tools (6)

- `get_content_by_id(id)` — page with body, ancestors, child pages, attachments
- `download_attachment(attachment_id)` — download attachment content
- `get_spaces()` — list spaces (key + name)
- `get_comments(id, depth, ...)` — footer + inline comments with markerRef/originalSelection, reply threads via parentId/replyCount. Pass comment ID to get its reply thread.
- `search(query, title, space_key, ...)` — full-text search with CQL filters
- `get_user(username | key)` — user profile: displayName, username, userKey

## Adding new tools

1. Find the endpoint in `api/confluence-openapi-v1.json` or `api/confluence-openapi-v2.json`
2. Add a `@mcp.tool(annotations=…)` async function in `server.py`, wrapped in `@_safe`
3. Use `conf.request(method, path, params=..., json_data=...)` for API calls, parsed by `_parse_response`
4. **Always post-process the response** — see "Output optimization" below
5. `expand` may be exposed as a parameter if the tool documents its default value and available fields (see `get_content_by_id`). Otherwise, hardcode it.
6. Closed value sets go in the signature as `Literal[...]`, numeric bounds as `Field(ge=…)`.
   Per-parameter prose goes in the `Args:` docstring section — fastmcp ≥3.4 parses it
   into the schema via griffe, so don't duplicate it in `Field(description=…)`.

### Tool template

```python
@mcp.tool(annotations={
    "title": "Human Readable Name",   # English, shown in tool lists
    "readOnlyHint": True,             # False if writing is the point of the tool
    "destructiveHint": False,
    "openWorldHint": True,            # every tool here talks to Confluence
})
@_safe
async def my_tool(param: str) -> str:
    """Short description for LLM.

    Args:
        param: what it means
    """
    raw = _parse_response(await conf.request("GET", f"/some/endpoint/{param}"))
    result = {
        "field1": raw.get("field1"),
        "field2": raw.get("nested", {}).get("field2"),
    }
    return json.dumps(result, ensure_ascii=False)
```

## Errors

One shape for every failure, returned as a normal result so the caller can
branch on a field instead of parsing free text out of a protocol error:

```json
{"error": "api_error", "message": "HTTP 403: ...", "status": 403}
```

`error` is one of `api_error` (HTTP or transport failure, carries `status` when
the server answered with a code), `bad_request` (a `ValueError` from the tool —
e.g. no search parameter given), `unexpected` (anything else). `_safe` wraps
every tool as a backstop; `_err_to_json` is the single formatter.

## CQL safety

`search` builds CQL by concatenation, so **every value must go through
`_cql_quote`** — it escapes `"` and `\`. A bare quote inside a value would close
the literal and let the rest be parsed as CQL, which means text an agent copied
off a page could change what the search means.

## Expand strategy

Each tool hardcodes a default `expand` value. `expand` may be exposed as a tool parameter
when documented (see `get_content_by_id`), but custom values may break post-processing
if expected fields are missing.

| Tool | expand | Why |
|---|---|---|
| `get_content_by_id` | `body.storage,version,history,space,ancestors,children.page,children.attachment` | Full page context for LLM |
| `get_comments` | `body.storage,version,extensions.inlineProperties,ancestors,children.comment` | Comment text + inline marker binding + reply tree |
| `search` | `space,version` | Lightweight results for listing |

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

**Exception:** `get_comments` keeps `_links.webui` as `link` field for direct comment navigation.

### What to keep

- Identifiers: `id`, `key` (spaces), `title`
- Content: `body.storage.value` (compact Confluence Storage Format HTML)
- Version: `version.number`, `version.when`, `version.by.displayName`
- Relationships: `ancestors[].{id,title}`, `childPages[].{id,title}`
- Attachments: `id`, `title`, `mediaType`, `fileSize`, `download` link
- Pagination: `start`, `size`, `totalSize`, `hasMore` — all four, from every paginated tool
  (`search`, `get_spaces`, `get_comments`). The names mirror Confluence's own contract;
  don't rename them. `totalSize` is `null` when the endpoint didn't send it.

### save_path

Read tools accept `save_path` to dump the JSON to a file instead of returning it.
Writing never overwrites: an existing name gets `(1)`, `(2)`, … appended
(`_unique_path`). Same for `download_attachment`.

### Why body.storage (not body.view)

- `body.storage` (~10KB) — compact XML with `<ac:*>` macros, PlantUML source
- `body.view` (~10KB) — rendered HTML, macros expanded, readable but larger
- `body.styled_view` (~80KB) — full HTML page with embedded CSS, never use
- `body.view` embeds base64 `data-diagramdata` blobs (~1.2KB each) for draw.io — pure noise for LLM
- `body.storage` keeps draw.io as a small `<ac:structured-macro>` tag (~200 bytes)

### Inline comments in body.storage

`body.storage` contains inline comment markers:
```xml
<ac:inline-comment-marker ac:ref="UUID">highlighted text</ac:inline-comment-marker>
```

`get_comments` returns `markerRef` (the UUID) for each inline comment — use it to locate
the exact position in page body. `originalSelection` is the text snapshot at comment creation time.

### Comment threads

- Top-level comments have `replyCount` (only if > 0) showing number of replies
- Reply comments have `parentId` pointing to the parent comment ID
- `depth` param: omit for top-level only, `"all"` to include replies (pages only, not comment threads)
- Pass a comment ID instead of page ID to `get_comments` to fetch a specific reply thread

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
