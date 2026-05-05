"""Minimal configuration for source fetchers, loaded from environment."""

import os


class SourceConfig:
    http_timeout: int = int(os.getenv("SOURCE_HTTP_TIMEOUT", "15"))
    gemini_timeout: int = int(os.getenv("SOURCE_GEMINI_TIMEOUT", "30"))

    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")

    github_min_stars: int = int(os.getenv("GITHUB_MIN_STARS", "50"))
    youtube_min_views: int = int(os.getenv("YOUTUBE_MIN_VIEWS", "1000"))
    hackernews_min_points: int = int(os.getenv("HACKERNEWS_MIN_POINTS", "5"))

    reddit_min_score: int = int(os.getenv("REDDIT_MIN_SCORE", "10"))
    reddit_user_agent: str = os.getenv("REDDIT_USER_AGENT", "aion-research/0.2")

    rss_min_relevance_score: float = float(os.getenv("RSS_MIN_RELEVANCE", "0.5"))


settings = SourceConfig()
