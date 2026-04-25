import requests
from typing import Optional, Literal
from langchain_core.tools import tool

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