"""Supabase JS-style API client (PostgREST, Auth, Storage, Realtime).

Use alongside SQLAlchemy + ``DATABASE_URL`` for Postgres: ORM queries stay in
``postgres.py``; use this client when you need ``.table(...).select()`` etc."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


@lru_cache(maxsize=1)
def get_supabase_client() -> Optional[Client]:
    """Return a cached Supabase client, or ``None`` if URL/key are unset."""
    url = os.getenv("SUPABASE_URL", "https://urjlnpjvrqbfylrwxlfc.supabase.co").strip()
    key = os.getenv("SUPABASE_KEY", "sb_publishable_nU-nF2jw9EfzLOO8fJ1mDw_pZja8lkU").strip()
    if not url or not key:
        return None
    return create_client(url, key)
