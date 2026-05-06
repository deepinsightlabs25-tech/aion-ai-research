"""Local source fetchers — direct API calls replacing the remote MCP hop."""

from .hackernews import search_hackernews
from .youtube import search_youtube
from .github import search_github
from .linkedin import search_google_linkedin
from .reddit import search_reddit
from .rss import search_rss
from .google_news import search_google_news
from .podcast import search_podcasts
from .arxiv import search_arxiv

__all__ = [
    "search_hackernews",
    "search_youtube",
    "search_github",
    "search_google_linkedin",
    "search_reddit",
    "search_rss",
    "search_google_news",
    "search_podcasts",
    "search_arxiv",
]
