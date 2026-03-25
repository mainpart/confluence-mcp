"""Confluence REST API MCP Server.

Wraps Confluence REST API v1 endpoints and exposes them as MCP tools.
Bearer-token (PAT) auth only.

API docs:
  v1: https://developer.atlassian.com/cloud/confluence/rest/v1/
  v2: https://developer.atlassian.com/cloud/confluence/rest/v2/
"""

import json
import logging
import os
import sys
from urllib.parse import urljoin

import httpx
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging — writes to stderr so it doesn't interfere with MCP stdio transport
# ---------------------------------------------------------------------------

log = logging.getLogger("confluence_mcp")
log.setLevel(os.environ.get("CONFLUENCE_LOG_LEVEL", "WARNING").upper())
if not log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"))
    log.addHandler(_handler)

# ---------------------------------------------------------------------------
# ConfluenceClient
# ---------------------------------------------------------------------------


class ConfluenceClient:
    def __init__(self, base_url: str, token: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verify_ssl = verify_ssl

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_data: dict | list | None = None,
        raw: bool = False,
    ) -> str | bytes:
        """Make an API request. Returns compact JSON string or error string.

        If *raw* is True, returns raw bytes (for file downloads).
        """
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        log.debug("%s %s params=%s", method, url, params)
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            try:
                resp = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=30.0,
                    follow_redirects=True,
                )
                log.debug("Response %s, %d bytes, content-type=%s",
                          resp.status_code, len(resp.content),
                          resp.headers.get("content-type", "?"))
                resp.raise_for_status()
                if raw:
                    return resp.content
                if not resp.content:
                    return '{"ok":true}'
                return json.dumps(resp.json(), separators=(",", ":"), ensure_ascii=False)
            except httpx.HTTPStatusError as e:
                body = e.response.text[:500] if e.response else ""
                log.warning("%s %s → HTTP %s: %s", method, path, e.response.status_code, body[:200])
                return f"HTTP {e.response.status_code}: {body}"
            except httpx.HTTPError as e:
                log.warning("%s %s → %s", method, path, e)
                return f"Error: {e}"
            except Exception as e:
                log.exception("%s %s → unexpected error", method, path)
                return f"Unexpected error: {e}"


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

conf = ConfluenceClient(
    base_url=os.environ.get("CONFLUENCE_URL", ""),
    token=os.environ.get("CONFLUENCE_TOKEN", ""),
    verify_ssl=os.environ.get("CONFLUENCE_VERIFY_SSL", "true").lower() not in ("false", "0", "no"),
)

mcp = FastMCP(
    "confluence",
    instructions=(
        "Confluence wiki tools. "
        "Inline comments: markerRef in get_comments output maps to "
        "<ac:inline-comment-marker ac:ref=\"UUID\"> elements in body.storage of the page."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ConfluenceAPIError(Exception):
    """Raised when conf.request() returns a non-JSON error string."""
    pass


def _parse_response(raw_str: str) -> dict | list:
    """Parse JSON response from conf.request(), raising on API errors.

    conf.request() returns valid compact JSON on success, or a plain-text
    error string (e.g. "HTTP 403: ...", "Error: ...") on failure.
    json.loads() on such strings produces the cryptic
    "Expecting value: line 1 column 1" — this helper gives a clear message.
    """
    try:
        return json.loads(raw_str)
    except (json.JSONDecodeError, ValueError):
        log.error("Non-JSON API response: %s", raw_str[:300])
        raise ConfluenceAPIError(raw_str)


def _maybe_save(json_str: str, save_path: str | None) -> str:
    """If save_path given, write JSON to file and return short confirmation."""
    if not save_path:
        return json_str
    try:
        save_path = os.path.abspath(save_path)
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            data = json.loads(json_str)
            json.dump(data, f, ensure_ascii=False, indent=2)
        size = os.path.getsize(save_path)
        return f"Saved to {save_path} ({size} bytes)"
    except Exception as e:
        return f"Error saving to {save_path}: {e}"


# ===========================================================================
# Content — Read
# ===========================================================================


@mcp.tool()
async def get_content_by_id(
    id: str,
    status: str | None = None,
    save_path: str | None = None,
) -> str:
    """Get content by ID. Returns title, body (storage format HTML), space, version, ancestors, child pages, attachments.

    Args:
        id: content ID
        save_path: if set, save JSON to this file instead of returning to LLM
    """
    params: dict = {"expand": "body.storage,version,history,space,ancestors,children.page,children.attachment"}
    if status:
        params["status"] = status
    raw = _parse_response(await conf.request("GET", f"/content/{id}", params=params))

    version = raw.get("version", {})
    history = raw.get("history", {})
    created_by = history.get("createdBy", {})
    space = raw.get("space", {})
    ancestors = raw.get("ancestors", [])
    attachments = raw.get("children", {}).get("attachment", {}).get("results", [])
    child_pages = raw.get("children", {}).get("page", {}).get("results", [])

    result: dict = {
        "id": raw.get("id"),
        "title": raw.get("title"),
        "status": raw.get("status"),
        "spaceKey": space.get("key"),
        "createdBy": created_by.get("displayName"),
        "createdByUsername": created_by.get("username"),
        "createdDate": history.get("createdDate"),
        "version": version.get("number"),
        "lastUpdated": version.get("when"),
        "lastUpdatedBy": version.get("by", {}).get("displayName"),
        "lastUpdatedByUsername": version.get("by", {}).get("username"),
        "ancestors": [{"id": a.get("id"), "title": a.get("title")} for a in ancestors],
        "childPages": [{"id": p.get("id"), "title": p.get("title")} for p in child_pages],
        "attachments": [
            {
                "id": a.get("id"),
                "title": a.get("title"),
                "mediaType": a.get("extensions", {}).get("mediaType"),
                "fileSize": a.get("extensions", {}).get("fileSize"),
                "download": a.get("_links", {}).get("download"),
            }
            for a in attachments
        ],
        "body": raw.get("body", {}).get("storage", {}).get("value", ""),
    }
    return _maybe_save(json.dumps(result, ensure_ascii=False), save_path)


# ===========================================================================
# Content — Attachments
# ===========================================================================


@mcp.tool()
async def download_attachment(
    id: str, attachment_id: str, save_path: str | None = None
) -> str:
    """Download attachment content.

    Args:
        id: page content ID (unused, kept for compatibility)
        attachment_id: the 'download' field from get_content_by_id attachments,
            e.g. "/download/attachments/123/file?version=1&api=v2"
        save_path: if set, save to this file instead of returning to LLM
    """
    url = urljoin(conf.base_url, attachment_id)
    headers = {"Authorization": f"Bearer {conf.token}"}
    async with httpx.AsyncClient(verify=conf.verify_ssl) as client:
        try:
            resp = await client.get(url, headers=headers, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            result = resp.content
        except httpx.HTTPError as e:
            return f"Error downloading: {e}"
    if isinstance(result, str):
        return result
    if save_path:
        try:
            save_path = os.path.abspath(save_path)
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(result)
            return f"Saved {len(result)} bytes to {save_path}"
        except OSError as e:
            return f"Error saving: {e}"
    try:
        return result.decode("utf-8")
    except UnicodeDecodeError:
        return f"(binary content, {len(result)} bytes). Use save_path to write to a file."


# ===========================================================================
# Spaces
# ===========================================================================


@mcp.tool()
async def get_spaces(
    space_key: str | None = None,
    status: str | None = None,
    label: str | None = None,
    favourite: bool | None = None,
    start: int | None = None,
    limit: int | None = None,
    save_path: str | None = None,
) -> str:
    """Get spaces. Returns key and name. Filter by space_key, status, label, favourite.

    Args:
        save_path: if set, save JSON to this file instead of returning to LLM
    """
    params = {}
    if space_key:
        params["spaceKey"] = space_key
    if status:
        params["status"] = status
    if label:
        params["label"] = label
    if favourite is not None:
        params["favourite"] = favourite
    if start is not None:
        params["start"] = start
    if limit is not None:
        params["limit"] = limit
    raw = _parse_response(await conf.request("GET", "/space", params=params))
    spaces = [{"key": s["key"], "name": s["name"]} for s in raw.get("results", [])]
    has_more = "next" in raw.get("_links", {})
    result = json.dumps(
        {"spaces": spaces, "start": raw.get("start"), "size": raw.get("size"), "hasMore": has_more},
        ensure_ascii=False,
    )
    return _maybe_save(result, save_path)


# ===========================================================================
# Comments
# ===========================================================================


@mcp.tool()
async def get_comments(
    id: str,
    depth: str | None = None,
    start: int | None = None,
    limit: int | None = None,
    save_path: str | None = None,
) -> str:
    """Get comments on a page or comment thread by content ID.

    Returns footer and inline comments. Inline comments have markerRef —
    UUID of <ac:inline-comment-marker> in page body.storage.
    Pass a comment ID to get its reply thread.

    Args:
        id: page content ID or comment ID (to get reply thread)
        depth: 'all' (include replies, default for pages) or '' (top-level only).
               Ignored when querying a comment thread.
        start: pagination offset
        limit: max results (default 25)
        save_path: if set, save JSON to this file instead of returning to LLM
    """
    params: dict = {"expand": "body.storage,version,extensions.inlineProperties,ancestors,children.comment"}
    if depth:
        params["depth"] = depth
    if start is not None:
        params["start"] = start
    if limit is not None:
        params["limit"] = limit
    raw = _parse_response(
        await conf.request("GET", f"/content/{id}/child/comment", params=params)
    )
    comments = []
    for c in raw.get("results", []):
        ver = c.get("version", {})
        ext = c.get("extensions", {})
        inline = ext.get("inlineProperties", {})
        location = ext.get("location", "footer")
        comment: dict = {
            "id": c.get("id"),
            "author": ver.get("by", {}).get("displayName"),
            "created": ver.get("when"),
            "location": location,
            "body": c.get("body", {}).get("storage", {}).get("value", ""),
            "link": c.get("_links", {}).get("webui"),
        }
        ancestors = c.get("ancestors", [])
        if ancestors:
            comment["parentId"] = ancestors[-1].get("id")
        reply_count = c.get("children", {}).get("comment", {}).get("size", 0)
        if reply_count:
            comment["replyCount"] = reply_count
        if location == "inline":
            if inline.get("markerRef"):
                comment["markerRef"] = inline["markerRef"]
            if inline.get("originalSelection"):
                comment["originalSelection"] = inline["originalSelection"]
        comments.append(comment)
    has_more = "next" in raw.get("_links", {})
    result = json.dumps(
        {
            "comments": comments,
            "start": raw.get("start"),
            "size": raw.get("size"),
            "hasMore": has_more,
        },
        ensure_ascii=False,
    )
    return _maybe_save(result, save_path)


# ===========================================================================
# Search
# ===========================================================================


@mcp.tool()
async def search(
    query: str | None = None,
    title: str | None = None,
    space_key: str | None = None,
    type: str | None = None,
    contributor: str | None = None,
    creator: str | None = None,
    label: str | None = None,
    ancestor: str | None = None,
    parent: str | None = None,
    created_from: str | None = None,
    modified_from: str | None = None,
    start: int | None = None,
    limit: int | None = None,
    save_path: str | None = None,
) -> str:
    """Search Confluence. All filters are combined with AND.
    For paginated results use start/limit params; check hasMore in the response.

    Args:
        query: full-text search
        title: title contains (fuzzy match)
        space_key: space key (exact)
        type: page, blogpost, comment, attachment
        contributor: username who edited
        creator: username who created
        label: page label
        ancestor: ancestor page ID (all descendants)
        parent: direct parent page ID
        created_from: created >= date (YYYY-MM-DD)
        modified_from: lastModified >= date (YYYY-MM-DD)
        save_path: if set, save JSON to this file instead of returning to LLM
    """
    cql_parts = []
    if query:
        cql_parts.append(f'text~"{query}"')
    if title:
        cql_parts.append(f'title~"{title}"')
    if space_key:
        cql_parts.append(f'space="{space_key}"')
    if type:
        cql_parts.append(f'type="{type}"')
    if contributor:
        cql_parts.append(f'contributor="{contributor}"')
    if creator:
        cql_parts.append(f'creator="{creator}"')
    if label:
        cql_parts.append(f'label="{label}"')
    if ancestor:
        cql_parts.append(f'ancestor="{ancestor}"')
    if parent:
        cql_parts.append(f'parent="{parent}"')
    if created_from:
        cql_parts.append(f'created>="{created_from}"')
    if modified_from:
        cql_parts.append(f'lastModified>="{modified_from}"')
    if not cql_parts:
        return json.dumps({"error": "Provide at least one search parameter"})
    params: dict = {"cql": " AND ".join(cql_parts), "expand": "space,version"}
    if start is not None:
        params["start"] = start
    if limit is not None:
        params["limit"] = limit
    raw = _parse_response(await conf.request("GET", "/content/search", params=params))
    results = []
    for item in raw.get("results", []):
        ver = item.get("version", {})
        results.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "type": item.get("type"),
            "spaceKey": item.get("space", {}).get("key"),
            "lastUpdated": ver.get("when"),
            "lastUpdatedBy": ver.get("by", {}).get("displayName"),
        })
    has_more = "next" in raw.get("_links", {})
    result = json.dumps(
        {"results": results, "start": raw.get("start"), "size": raw.get("size"), "totalSize": raw.get("totalSize"), "hasMore": has_more},
        ensure_ascii=False,
    )
    return _maybe_save(result, save_path)


# ===========================================================================
# Users
# ===========================================================================


@mcp.tool()
async def get_user(
    username: str | None = None,
    key: str | None = None,
) -> str:
    """Get user profile by username or userKey. Returns displayName, username, userKey.

    Args:
        username: Confluence username (e.g. U_M2P0J). From page URLs like /display/~U_M2P0J
        key: Confluence userKey (e.g. 2c9cfcaa997c4dad...). From ri:userkey in page body HTML
    """
    if not username and not key:
        return json.dumps({"error": "Provide username or key"})
    params = {}
    if username:
        params["username"] = username
    elif key:
        params["key"] = key
    raw = _parse_response(await conf.request("GET", "/user", params=params))
    return json.dumps(
        {
            "displayName": raw.get("displayName"),
            "username": raw.get("username"),
            "userKey": raw.get("userKey"),
        },
        ensure_ascii=False,
    )


# ===========================================================================
# Entry point
# ===========================================================================


def main():
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    kwargs = {}
    if transport in ("sse", "streamable-http"):
        kwargs["host"] = os.environ.get("MCP_HOST", "0.0.0.0")
        kwargs["port"] = int(os.environ.get("MCP_PORT", "8000"))
    mcp.run(transport=transport, **kwargs)


if __name__ == "__main__":
    main()
