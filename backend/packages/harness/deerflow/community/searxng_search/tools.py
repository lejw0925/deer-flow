"""
Web Search Tool - Search the web using a local SearXNG instance.

No external API key required. SearXNG runs locally and proxies search
requests through the host's HTTP_PROXY / HTTPS_PROXY.
"""

import json
import logging

import httpx
from langchain.tools import tool

from deerflow.config import get_app_config

logger = logging.getLogger(__name__)

# Default SearXNG URL (reachable via Docker host proxy port)
DEFAULT_SEARXNG_URL = "http://host.docker.internal:8081"


def _search_text(
    query: str,
    max_results: int = 5,
    searxng_url: str = DEFAULT_SEARXNG_URL,
    language: str = "zh-CN",
    categories: str = "general",
    timeout: int = 30,
) -> list[dict]:
    """
    Execute text search using local SearXNG instance.

    Args:
        query: Search keywords
        max_results: Maximum number of results
        searxng_url: Base URL of the SearXNG instance
        language: Search language code
        categories: Search categories (general, news, science, etc.)
        timeout: Request timeout in seconds

    Returns:
        List of normalized search results
    """
    try:
        # NOTE: httpx in sync mode; SearXNG responses are small enough
        # that blocking the event loop briefly is acceptable.
        response = httpx.get(
            f"{searxng_url}/search",
            params={
                "q": query,
                "format": "json",
                "language": language,
                "categories": categories,
                "safesearch": "0",
                "pageno": "1",
            },
            timeout=timeout,
            headers={
                "User-Agent": "deerflow-searxng/1.0",
            },
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        return results[:max_results] if results else []

    except httpx.HTTPError as e:
        logger.error(f"SearXNG request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"SearXNG search failed: {e}")
        return []


@tool("web_search", parse_docstring=True)
async def web_search_tool(
    query: str,
    max_results: int = 5,
) -> str:
    """Search the web for information. Use this tool to find current information, news, articles, and facts from the internet.

    Args:
        query: Search keywords describing what you want to find. Be specific for better results.
        max_results: Maximum number of results to return. Default is 5.
    """
    import asyncio

    config = get_app_config().get_tool_config("web_search")

    # Override from config if set
    searxng_url = DEFAULT_SEARXNG_URL
    language = "zh-CN"
    if config is not None and "searxng_url" in config.model_extra:
        searxng_url = config.model_extra.get("searxng_url")
    if config is not None and "max_results" in config.model_extra:
        max_results = config.model_extra.get("max_results", max_results)

    results = await asyncio.to_thread(
        _search_text,
        query=query,
        max_results=max_results,
        searxng_url=searxng_url,
        language=language,
    )

    if not results:
        return json.dumps(
            {"error": "No results found", "query": query}, ensure_ascii=False
        )

    normalized_results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", r.get("snippet", "")),
        }
        for r in results
    ]

    output = {
        "query": query,
        "total_results": len(normalized_results),
        "results": normalized_results,
    }

    return json.dumps(output, indent=2, ensure_ascii=False)
