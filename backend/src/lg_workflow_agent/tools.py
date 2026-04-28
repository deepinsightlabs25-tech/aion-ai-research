"""Tools for the lg_workflow_agent workflow.

Re-exports `fetch_trends` from the existing agent toolkit and adds a link
validator used by the Validator node to detect broken references.
"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse
from typing import Optional, Literal
from langchain_core.tools import tool


import requests


__all__ = ["fetch_trends", "think_tool", "validate_url", "validate_urls"]

API_BASE_URL = "https://research-mcp-9mm5.onrender.com"

# The available sources according to the API docs
SOURCES = Literal[
    "hackernews",
    "youtube",
    "github",
    "google-linkedin",
    "reddit",
    "rss",
    "google-news",
    "podcasts",
    "arxiv"
]

import json

@tool
def fetch_trends(source: str, topic: str = "", limit: int = 10, period: str = "week") -> str:
    """
    Fetches trending data on a specific topic from various sources.
    
    Args:
        source: The data source to query ('hackernews', 'youtube', 'github', 
                'google-linkedin', 'reddit', 'rss', 'google-news', 'podcasts', 'arxiv').
                Alternatively, this can be a JSON string containing source, topic, limit, period.
        topic: The search topic.
        limit: Limit results.
        period: Time period.
    """
    try:
        data = json.loads(source)
        source = data.get("source", "")
        topic = data.get("topic", topic)
        limit = data.get("limit", limit)
        period = data.get("period", period)
    except Exception:
        pass
        
    url = f"{API_BASE_URL}/trends/{source}"
    payload = {
        "topic": topic,
        "limit": limit,
        "period": period
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return "{}"

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





_URL_RE = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    """Extract HTTP/HTTPS URLs from a piece of text."""
    return list({m.group(0).rstrip(".,);]") for m in _URL_RE.finditer(text or "")})


def validate_url(url: str, timeout: float = 6.0) -> bool:
    """Return True if the URL responds with a non-error HTTP status.

    Falls back to GET if HEAD is not allowed by the server.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        if resp.status_code in {405, 403}:  # some servers reject HEAD
            resp = requests.get(url, allow_redirects=True, timeout=timeout, stream=True)
        return 200 <= resp.status_code < 400
    except Exception:
        return False


def validate_urls(urls: Iterable[str]) -> dict[str, bool]:
    """Validate many URLs and return a {url: ok} mapping."""
    return {u: validate_url(u) for u in urls}