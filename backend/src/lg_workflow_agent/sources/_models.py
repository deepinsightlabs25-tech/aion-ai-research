"""Lightweight data models for source results."""

from datetime import datetime

from pydantic import BaseModel, Field


class TrendItem(BaseModel):
    title: str
    url: str
    source: str
    metadata: dict = Field(default_factory=dict)


class SourceResult(BaseModel):
    results: list[TrendItem]
    source: str
    query: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    error: str | None = None
