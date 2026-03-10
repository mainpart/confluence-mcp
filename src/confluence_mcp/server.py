"""Confluence REST API MCP Server.

Wraps Confluence REST API v1 endpoints and exposes them as MCP tools.
Bearer-token (PAT) auth only.

API docs:
  v1: https://developer.atlassian.com/cloud/confluence/rest/v1/
  v2: https://developer.atlassian.com/cloud/confluence/rest/v2/
"""

import json
import os

import httpx
from fastmcp import FastMCP

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
                resp.raise_for_status()
                if raw:
                    return resp.content
                if not resp.content:
                    return '{"ok":true}'
                return json.dumps(resp.json(), separators=(",", ":"), ensure_ascii=False)
            except httpx.HTTPStatusError as e:
                body = e.response.text[:500] if e.response else ""
                return f"HTTP {e.response.status_code}: {body}"
            except httpx.HTTPError as e:
                return f"Error: {e}"
            except Exception as e:
                return f"Unexpected error: {e}"


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

conf = ConfluenceClient(
    base_url=os.environ.get("CONFLUENCE_URL", ""),
    token=os.environ.get("CONFLUENCE_TOKEN", ""),
    verify_ssl=os.environ.get("CONFLUENCE_VERIFY_SSL", "true").lower() not in ("false", "0", "no"),
)

mcp = FastMCP("confluence")


# ===========================================================================
# Content — Read
# ===========================================================================


@mcp.tool()
async def get_content_by_id(
    id: str,
    expand: str | None = None,
    status: str | None = None,
) -> str:
    """Get content by ID. expand: e.g. 'body.storage,version,space'. status: current/trashed/draft."""
    params = {}
    if expand:
        params["expand"] = expand
    if status:
        params["status"] = status
    return await conf.request("GET", f"/content/{id}", params=params)


# ===========================================================================
# Content — Attachments
# ===========================================================================


@mcp.tool()
async def download_attachment(
    id: str, attachment_id: str, save_path: str | None = None
) -> str:
    """Download attachment. Returns text content or saves to save_path for binary files."""
    result = await conf.request(
        "GET", f"/content/{id}/child/attachment/{attachment_id}/download", raw=True
    )
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
    type: str | None = None,
    status: str | None = None,
    label: str | None = None,
    favourite: bool | None = None,
    expand: str | None = None,
    start: int | None = None,
    limit: int | None = None,
) -> str:
    """Get spaces. Filter by space_key, type (global/personal), status, label, favourite."""
    params = {}
    if space_key:
        params["spaceKey"] = space_key
    if type:
        params["type"] = type
    if status:
        params["status"] = status
    if label:
        params["label"] = label
    if favourite is not None:
        params["favourite"] = favourite
    if expand:
        params["expand"] = expand
    if start is not None:
        params["start"] = start
    if limit is not None:
        params["limit"] = limit
    return await conf.request("GET", "/space", params=params)


# ===========================================================================
# Search
# ===========================================================================


@mcp.tool()
async def search_content(
    query: str,
    space_key: str | None = None,
    type: str | None = None,
    expand: str | None = None,
    start: int | None = None,
    limit: int | None = None,
) -> str:
    """Search content. query: text to search for. Optionally filter by space_key and type (page/blogpost/comment/attachment)."""
    cql_parts = [f'text~"{query}"']
    if space_key:
        cql_parts.append(f'space="{space_key}"')
    if type:
        cql_parts.append(f'type="{type}"')
    cql = " AND ".join(cql_parts)
    params: dict = {"cql": cql}
    if expand:
        params["expand"] = expand
    if start is not None:
        params["start"] = start
    if limit is not None:
        params["limit"] = limit
    return await conf.request("GET", "/content/search", params=params)


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
