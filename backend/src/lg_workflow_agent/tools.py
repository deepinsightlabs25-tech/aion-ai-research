"""Tools for the lg_workflow_agent workflow.

Re-exports `fetch_trends` from the existing agent toolkit and adds a link
validator used by the Validator node to detect broken references.
"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

import requests

from src.agent.tools import fetch_trends, think_tool

__all__ = ["fetch_trends", "think_tool", "validate_url", "validate_urls"]


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