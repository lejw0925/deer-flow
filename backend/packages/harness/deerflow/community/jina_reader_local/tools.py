"""Local Jina Reader web fetch tool — calls self-hosted reader service.

No external API key required. The jina-reader container runs inside the
deer-flow Docker network and handles rendering + readability extraction.

NOTE: httpx/requests/urllib return 502 from jina-reader OSS for unknown reasons.
We use http.client directly (sync) wrapped in asyncio.to_thread for async compat.
"""
import asyncio
import http.client
import logging
import urllib.parse

from langchain.tools import tool

from deerflow.config import get_app_config

logger = logging.getLogger(__name__)

# Default to the service name inside the Docker network
DEFAULT_READER_URL = "http://jina-reader:8081"


def _fetch_sync(fetch_url: str, timeout: int) -> tuple[int, str]:
    """Synchronous fetch using http.client — works with jina-reader OSS."""
    parsed = urllib.parse.urlparse(fetch_url)
    host = parsed.hostname or "jina-reader"
    port = parsed.port or 8081
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request(
            "GET",
            path,
            headers={
                "Host": f"{host}:{port}",
                "User-Agent": "deerflow-web-fetch/1.0",
                "Accept": "text/plain, text/html, */*",
                "Connection": "close",
            },
        )
        response = conn.getresponse()
        status = response.status
        body = response.read().decode("utf-8", errors="replace")
        return status, body
    finally:
        conn.close()


@tool("web_fetch", parse_docstring=True)
async def web_fetch_tool(url: str) -> str:
    """Fetch the contents of a web page at a given URL.
    Only fetch EXACT URLs that have been provided directly by the user or have been returned in results from the web_search and web_fetch tools.
    This tool can NOT access content that requires authentication, such as private Google Docs or pages behind login walls.
    Do NOT add www. to URLs that do NOT have them.
    URLs must include the schema: https://example.com is a valid URL while example.com is an invalid URL.

    Args:
        url: The URL to fetch the contents of.
    """
    config = get_app_config().get_tool_config("web_fetch")
    reader_base = DEFAULT_READER_URL
    timeout = 30

    if config is not None:
        if "reader_url" in config.model_extra:
            reader_base = config.model_extra.get("reader_url")
        if "timeout" in config.model_extra:
            timeout = config.model_extra.get("timeout")

    # Jina Reader API: prepend base URL to target URL
    fetch_url = f"{reader_base}/{url}"

    try:
        status, body = await asyncio.to_thread(_fetch_sync, fetch_url, timeout)

        if status != 200:
            error_message = f"Reader returned HTTP {status}: {body[:500]}"
            logger.warning("web_fetch failed | url=%s | status=%d | error=%s", url, status, error_message)
            return f"Error: {error_message}"

        if not body or not body.strip():
            return "Error: Empty response from reader"

        # Truncate to 4096 chars to match existing behaviour
        return body[:4096]

    except Exception as e:
        error_message = f"Request failed: {type(e).__name__}: {e}"
        logger.warning("web_fetch failed | url=%s | error=%s", url, error_message)
        return f"Error: {error_message}"
