"""Free web fetch tool — no external API required.

Uses httpx to fetch raw HTML and readabilipy for content extraction.
"""
import asyncio
import logging

import httpx
from langchain.tools import tool

from deerflow.config import get_app_config
from deerflow.utils.readability import ReadabilityExtractor

logger = logging.getLogger(__name__)
readability_extractor = ReadabilityExtractor()


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
    timeout = 10
    config = get_app_config().get_tool_config("web_fetch")
    if config is not None and "timeout" in config.model_extra:
        timeout = config.model_extra.get("timeout")

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=timeout, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            })

        if response.status_code != 200:
            error_message = f"HTTP {response.status_code} for {url}"
            logger.warning(error_message)
            return f"Error: {error_message}"

        if not response.text or not response.text.strip():
            return "Error: Empty response"

        article = await asyncio.to_thread(readability_extractor.extract_article, response.text)
        return article.to_markdown()[:4096]

    except Exception as e:
        error_message = f"Request failed: {type(e).__name__}: {e}"
        logger.warning(error_message)
        return f"Error: {error_message}"
