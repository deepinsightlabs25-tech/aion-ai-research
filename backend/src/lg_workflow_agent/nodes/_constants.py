"""Shared constants for node factories."""

from __future__ import annotations

from ..prompts import (
    CITATION_PROMPT,
    DATA_COLLECTION_PROMPT,
    LATEST_NEWS_COLLECTION_PROMPT,
    STATISTICS_PROMPT,
    WEB_RESEARCH_PROMPT,
)

# Map of role -> sub-agent system prompt.
ROLE_PROMPTS: dict[str, str] = {
    # deep_research roles
    "data_collection": DATA_COLLECTION_PROMPT,
    "statistics": STATISTICS_PROMPT,
    "citation": CITATION_PROMPT,
    # non-deep roles
    "web_research": WEB_RESEARCH_PROMPT,
    "latest_news_collection": LATEST_NEWS_COLLECTION_PROMPT,
}

# Roles available per query type.
ROLES_BY_TYPE: dict[str, list[str]] = {
    "deep_research": ["data_collection", "statistics", "citation"],
    "blog": ["web_research", "latest_news_collection"],
    "comparative": ["web_research", "latest_news_collection"],
    "summary": ["web_research", "latest_news_collection"],
}

MAX_REWRITES = 2
