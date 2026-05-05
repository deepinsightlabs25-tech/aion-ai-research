"""Verify all source tools are callable and return valid SourceResult data.

Run:
    cd backend && uv run python tests/test_sources.py

Each tool is called with a test topic. The script prints a summary table
showing which tools succeeded, how many results they returned, and timing.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.lg_workflow_agent.sources import (
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

TEST_TOPIC = "AI agents"
TEST_LIMIT = 3

SOURCES = [
    ("fetch_hackernews", lambda: search_hackernews(TEST_TOPIC, TEST_LIMIT, "week")),
    ("fetch_youtube", lambda: search_youtube(TEST_TOPIC, TEST_LIMIT)),
    ("fetch_github", lambda: search_github(TEST_TOPIC, TEST_LIMIT)),
    ("fetch_linkedin", lambda: search_google_linkedin(TEST_TOPIC, TEST_LIMIT)),
    ("fetch_reddit", lambda: search_reddit(TEST_TOPIC, TEST_LIMIT)),
    ("fetch_rss", lambda: search_rss(TEST_TOPIC, TEST_LIMIT)),
    ("fetch_google_news", lambda: search_google_news(TEST_TOPIC, TEST_LIMIT)),
    ("fetch_podcasts", lambda: search_podcasts(TEST_TOPIC, TEST_LIMIT)),
    ("fetch_arxiv", lambda: search_arxiv(TEST_TOPIC, TEST_LIMIT)),
]


async def test_source(name: str, coro_fn):
    start = time.perf_counter()
    try:
        result = await coro_fn()
        elapsed = time.perf_counter() - start
        count = len(result.results)
        error = result.error
        if error:
            return name, "WARN", 0, elapsed, error
        return name, "OK", count, elapsed, None
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return name, "FAIL", 0, elapsed, str(exc)


async def main():
    print(f"\n{'='*70}")
    print(f"  Source Tools Verification — topic: \"{TEST_TOPIC}\", limit: {TEST_LIMIT}")
    print(f"{'='*70}\n")

    results = await asyncio.gather(*[test_source(name, fn) for name, fn in SOURCES])

    print(f"  {'Tool':<20} {'Status':<8} {'Results':<10} {'Time':<10} {'Error'}")
    print(f"  {'-'*20} {'-'*8} {'-'*10} {'-'*10} {'-'*30}")

    passed = 0
    warned = 0
    failed = 0

    for name, status, count, elapsed, error in results:
        error_display = (error[:40] + "...") if error and len(error) > 40 else (error or "")
        status_icon = {"OK": "OK", "WARN": "WARN", "FAIL": "FAIL"}[status]
        print(f"  {name:<20} {status_icon:<8} {count:<10} {elapsed:<10.2f} {error_display}")

        if status == "OK":
            passed += 1
        elif status == "WARN":
            warned += 1
        else:
            failed += 1

    print(f"\n{'='*70}")
    print(f"  Summary: {passed} passed, {warned} warnings, {failed} failed (out of {len(SOURCES)})")
    print(f"{'='*70}\n")

    # Print sample data from first successful result
    for name, status, count, elapsed, error in results:
        if status == "OK" and count > 0:
            idx = next(i for i, (n, _) in enumerate(SOURCES) if n == name)
            result = await SOURCES[idx][1]()
            print(f"  Sample from {name}:")
            for item in result.results[:2]:
                print(f"    - {item.title[:60]}")
                print(f"      {item.url[:80]}")
                print(f"      metadata keys: {list(item.metadata.keys())}")
            print()
            break

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
