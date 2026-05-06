"""Tools for the lg_workflow_agent workflow.

Provides individual source-fetching tools (direct API calls, no MCP hop),
a think_tool for sub-agent reflection, and URL validation utilities used
by the Validator node.
"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

import requests
from langchain_core.tools import tool

from .sources import (
    search_arxiv,
    search_github,
    search_google_linkedin,
    search_google_news,
    search_hackernews,
    search_podcasts,
    search_reddit,
    search_rss,
    search_youtube,
)

__all__ = [
    "fetch_hackernews",
    "fetch_youtube",
    "fetch_github",
    "fetch_linkedin",
    "fetch_reddit",
    "fetch_rss",
    "fetch_google_news",
    "fetch_podcasts",
    "fetch_arxiv",
    "think_tool",
    "validate_url",
    "validate_urls",
]


# ---------------------------------------------------------------------------
# Individual source tools — native async (no thread pool needed).
# LangChain @tool supports async def directly; runs on the caller's loop.
# ---------------------------------------------------------------------------


@tool
async def fetch_hackernews(topic: str, limit: int = 10, period: str = "week") -> str:
    """Search Hacker News for trending stories about a topic, sorted by points.

    Args:
        topic: The topic to search for (e.g. "AI agents", "React", "startup funding")
        limit: Maximum number of results to return (default: 10)
        period: Time window — "week", "month", or "quarter" (default: "week")
    """
    result = await search_hackernews(topic, limit, period)
    return result.model_dump_json()


@tool
async def fetch_youtube(topic: str, limit: int = 10) -> str:
    """Search YouTube for trending videos about a topic from the last 7 days.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_youtube(topic, limit)
    return result.model_dump_json()


@tool
async def fetch_github(topic: str, limit: int = 10) -> str:
    """Search GitHub for trending repositories about a topic, sorted by stars/day growth.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_github(topic, limit)
    return result.model_dump_json()


@tool
async def fetch_linkedin(topic: str, limit: int = 10) -> str:
    """Search for trending LinkedIn posts and articles about a topic via Google Search.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_google_linkedin(topic, limit)
    return result.model_dump_json()


@tool
async def fetch_reddit(topic: str, limit: int = 10, period: str = "week") -> str:
    """Search Reddit for trending discussions about a topic, sorted by engagement.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
        period: Time window — "week", "month", or "quarter" (default: "week")
    """
    result = await search_reddit(topic, limit, period)
    return result.model_dump_json()


@tool
async def fetch_rss(topic: str, limit: int = 10) -> str:
    """Search curated industry publications (TechCrunch, HubSpot, SaaStr, The Verge, etc.) for articles about a topic.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_rss(topic, limit)
    return result.model_dump_json()


@tool
async def fetch_google_news(topic: str, limit: int = 10) -> str:
    """Search Google News for trending articles about a topic from thousands of publications.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_google_news(topic, limit)
    return result.model_dump_json()


@tool
async def fetch_podcasts(topic: str, limit: int = 10) -> str:
    """Search for trending podcast episodes about a topic from iTunes/Apple Podcasts.

    Args:
        topic: The topic to search for
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_podcasts(topic, limit)
    return result.model_dump_json()


@tool
async def fetch_arxiv(topic: str, limit: int = 10) -> str:
    """Search arXiv for recent academic papers about a topic (last 7-30 days).

    Useful for citing scholarly work and understanding the research landscape.

    Args:
        topic: The topic to search for (e.g. "large language models", "reinforcement learning")
        limit: Maximum number of results to return (default: 10)
    """
    result = await search_arxiv(topic, limit)
    return result.model_dump_json()


# ---------------------------------------------------------------------------
# Think tool (sub-agent reflection)
# ---------------------------------------------------------------------------


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"


# ---------------------------------------------------------------------------
# URL validation (used by the Validator node, not exposed as agent tools)
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    """Extract HTTP/HTTPS URLs from a piece of text."""
    return list({m.group(0).rstrip(".,);]") for m in _URL_RE.finditer(text or "")})


def validate_url(url: str, timeout: float = 6.0) -> bool:
    """Return True if the URL responds with a non-error HTTP status."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        if resp.status_code in {405, 403}:
            resp.close()
            with requests.get(url, allow_redirects=True, timeout=timeout, stream=True) as r:
                return 200 <= r.status_code < 400
        status_ok = 200 <= resp.status_code < 400
        resp.close()
        return status_ok
    except Exception:
        return False


def validate_urls(urls: Iterable[str]) -> dict[str, bool]:
    """Validate many URLs and return a {url: ok} mapping."""
    return {u: validate_url(u) for u in urls}
