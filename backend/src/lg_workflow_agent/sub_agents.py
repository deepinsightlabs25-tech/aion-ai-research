"""Deterministic sub-agent runners for the lg_workflow_agent workflow.

Each role runner performs a fixed two-step flow (no ReAct loop):

    1. Ask the LLM to generate a small set of focused search queries based on
       the user query and the assigned sub-task.
    2. For every (source, query) pair allowed for the role, directly invoke
       :func:`fetch_trends` and collect the results. Empty responses or
       errors are silently dropped.

The collected, structured findings are returned as the ``worker_outputs``
state update consumed downstream by the aggregator.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable

from .tools import fetch_trends

__all__ = ["build_role_runners"]


# Role -> ordered list of `fetch_trends` sources that are appropriate for it.
ROLE_SOURCES: dict[str, list[str]] = {
    # Deep-research roles
    "data_collection": ["arxiv", "google-news", "hackernews", "github"],
    "statistics": ["google-news", "arxiv", "hackernews"],
    "citation": ["arxiv", "github"],
    # Lightweight roles
    "web_research": ["google-news", "hackernews", "reddit"],
    "latest_news_collection": ["google-news", "hackernews", "reddit", "rss"],
}

# Per-role default knobs.
_DEFAULT_NUM_QUERIES = 5
_DEFAULT_LIMIT = 10
_DEFAULT_PERIOD = "week"
_MAX_ITEMS_PER_ROLE = 10


QUERY_GEN_PROMPT = """You are the query-generation step for a research sub-agent.

Sub-agent role: {role}
Allowed data sources: {sources}
User query: {query}
Sub-task: {task}

Produce {n} concise, diverse search queries that — when executed against the
allowed data sources — will surface useful results for this sub-task.

Rules:
- Each query should be 2-8 keywords (no full sentences, no question marks).
- Queries must be diverse: cover different angles / facets of the sub-task.
- Stay strictly on-topic with respect to the user query and sub-task.

Return STRICT JSON only, no prose, no fences:
{{"queries": ["query 1", "query 2", "..."]}}
"""


# Per-role guidance for the short report summarizer. Keeps each sub-agent's
# output focused on the kind of evidence the aggregator/writer needs.
_ROLE_REPORT_GUIDANCE: dict[str, str] = {
    "data_collection": (
        "Focus on PRIMARY facts, definitions, technical details, and concrete "
        "claims drawn from the sources. Be dense and specific."
    ),
    "statistics": (
        "Focus on QUANTITATIVE data: numbers, percentages, growth rates, "
        "benchmarks, dates, and dollar figures. Quote exact numbers from the "
        "snippets — never invent or estimate. If a snippet has no numbers, "
        "skip it. Each statistic MUST be followed by an inline [n] citation."
    ),
    "citation": (
        "Focus on identifying high-signal references (papers, official docs, "
        "standards) and one-line notes on what each covers. No prose."
    ),
    "web_research": (
        "Focus on a balanced overview of the topic with diverse perspectives, "
        "grounded in the sources. Inline [n] citations are mandatory."
    ),
    "latest_news_collection": (
        "Recent news only. Keep entries terse with date + source."
    ),
}


DETAILED_REPORT_PROMPT = """You are the report-writing step for a research sub-agent.

Sub-agent role: {role}
User query: {query}
Sub-task: {task}

Role guidance:
{guidance}

You are given a JSON list of source items collected by the search step.
Each item has: id, title, url, snippet, source, published.

Write a VERY DETAILED, comprehensive, and source-grounded report that the
downstream aggregator and writer can build a massive final report from. 
Include all useful insights, data points, quotes, and statistics found in the snippets.

HARD RULES:
- Use ONLY information present in the snippets. Do NOT add outside knowledge.
- Extract maximum possible detail from the provided snippets. Do not summarize away important facts.
- Every factual claim or number MUST end with an inline [n] citation, where n
  is the item's id.
- Do NOT invent statistics, dates, or quotes. If a snippet has none, omit.
- Do NOT mention tool names, sub-agents, "the data shows", "according to my
  research", or any meta-commentary about the process.
- Do NOT apologize for missing data; just write what is supported.

Output format — return EXACTLY this Markdown structure, nothing else:

## Findings
<comprehensive, highly detailed paragraphs of facts and analysis with inline [n] citations>

## Sources
[1] <title> - <url>
[2] <title> - <url>
...

The "Sources" list MUST include every id you cited, in ascending order, and
MUST use the same id numbers that appear in the input items.

Source items (JSON):
{items}
"""


# --------------------------- helpers ---------------------------------------


def _safe_json_load(text: str) -> dict:
    """Tolerant JSON loader that strips ```json fences and extracts the
    first object if needed."""
    if not text:
        return {}
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
        return {}


def _generate_queries(llm, role: str, query: str, task: str,
                      sources: list[str], n: int) -> list[str]:
    """Ask the LLM for a small list of search queries. Falls back to the
    sub-task / user query on any failure."""
    prompt = QUERY_GEN_PROMPT.format(
        role=role,
        sources=", ".join(sources),
        query=query,
        task=task,
        n=n,
    )
    fallback = [q for q in (task, query) if q]
    try:
        response = llm.invoke(prompt)
        content = getattr(response, "content", "") or ""
        if isinstance(content, list):
            content = next(
                (p.get("text", "") for p in content if isinstance(p, dict) and p.get("text")),
                "",
            )
        parsed = _safe_json_load(content)
        queries = parsed.get("queries") if isinstance(parsed, dict) else None
        if not isinstance(queries, list):
            return fallback or [""]
        cleaned: list[str] = []
        seen: set[str] = set()
        for q in queries:
            if not isinstance(q, str):
                continue
            q = q.strip()
            if not q or q.lower() in seen:
                continue
            seen.add(q.lower())
            cleaned.append(q)
        return cleaned[:n] if cleaned else (fallback or [""])
    except Exception:
        return fallback or [""]


def _parse_tool_payload(raw: str) -> list[dict[str, Any]]:
    """Parse a `fetch_trends` response into a list of item dicts.

    Returns ``[]`` for any error / empty / unrecognized payload.
    """
    if not raw or not isinstance(raw, str):
        return []
    raw = raw.strip()
    if not raw or raw in {"{}", "[]", "null"}:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []

    candidates: Iterable[Any]
    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict):
        # Common shapes: {"results": [...]}, {"items": [...]}, {"data": [...]}
        for key in ("results", "items", "data", "entries"):
            v = data.get(key)
            if isinstance(v, list):
                candidates = v
                break
        else:
            # Single-item dict — keep it if it has a url/link.
            candidates = [data] if any(k in data for k in ("url", "link")) else []
    else:
        return []

    items: list[dict[str, Any]] = []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        url = c.get("url") or c.get("link") or c.get("permalink") or ""
        if not url or not isinstance(url, str):
            continue
        items.append(
            {
                "title": (c.get("title") or c.get("name") or "").strip(),
                "url": url.strip(),
                "snippet": (
                    c.get("snippet")
                    or c.get("description")
                    or c.get("summary")
                    or c.get("text")
                    or ""
                ).strip(),
                "published": (
                    c.get("published_at")
                    or c.get("published")
                    or c.get("date")
                    or ""
                ),
            }
        )
    return items


def _collect(queries: list[str], sources: list[str],
             limit: int, period: str) -> list[dict[str, Any]]:
    """Call `fetch_trends` for every (source, query) pair and aggregate
    non-empty results. Drops duplicates by URL."""
    seen_urls: set[str] = set()
    collected: list[dict[str, Any]] = []
    for q in queries:
        if not q:
            continue
        for source in sources:
            try:
                raw = fetch_trends.invoke(
                    {
                        "source": source,
                        "topic": q,
                        "limit": limit,
                        "period": period,
                    }
                )
            except Exception:
                continue
            items = _parse_tool_payload(raw)
            if not items:
                continue
            for it in items:
                url = it["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                it["source"] = source
                it["query"] = q
                collected.append(it)
                if len(collected) >= _MAX_ITEMS_PER_ROLE:
                    return collected
    return collected


def _format_findings(role: str, items: list[dict[str, Any]]) -> str:
    """Render collected items as deterministic markdown for the aggregator.

    Shape:
      - ``latest_news_collection`` -> ``## Latest News`` bullet list.
      - all other roles -> ``## Findings`` block plus a ``## Sources`` block.
    """
    if not items:
        return ""

    if role == "latest_news_collection":
        lines = ["## Latest News"]
        for it in items:
            title = it["title"] or it["url"]
            snippet = (it["snippet"] or "").replace("\n", " ").strip()
            if len(snippet) > 200:
                snippet = snippet[:197].rstrip() + "..."
            date = (it.get("published") or "").strip()
            date_part = f", {date[:10]}" if date else ""
            tail = f" — {snippet}" if snippet else ""
            lines.append(
                f"- [{title}]({it['url']}){tail} ({it['source']}{date_part})"
            )
        return "\n".join(lines)

    finding_lines: list[str] = ["## Findings"]
    source_lines: list[str] = ["## Sources"]
    for idx, it in enumerate(items, start=1):
        title = it["title"] or it["url"]
        snippet = (it["snippet"] or "").replace("\n", " ").strip()
        if snippet:
            if len(snippet) > 800:
                snippet = snippet[:797].rstrip() + "..."
            finding_lines.append(f"- {title}: {snippet} [{idx}]")
        else:
            finding_lines.append(f"- {title} [{idx}]")
        source_lines.append(f"[{idx}] {title} - {it['url']}")
    return "\n".join(finding_lines) + "\n\n" + "\n".join(source_lines)


def _write_short_report(
    llm,
    role: str,
    query: str,
    task: str,
    items: list[dict[str, Any]],
) -> str:
    """Ask the LLM to synthesise a short, source-grounded report from the
    collected items. Falls back to :func:`_format_findings` on any failure.

    The ``latest_news_collection`` role bypasses the LLM entirely — its output
    is meant to be a deterministic news bullet list, not prose.
    """
    fallback = _format_findings(role, items)
    if role == "latest_news_collection" or not items:
        return fallback

    # Build a compact, id-numbered payload for the LLM. Truncate fields to
    # keep prompt size bounded.
    numbered: list[dict[str, Any]] = []
    for idx, it in enumerate(items, start=1):
        title = (it.get("title") or it.get("url") or "").strip()[:200]
        snippet = (it.get("snippet") or "").replace("\n", " ").strip()[:1500]
        numbered.append(
            {
                "id": idx,
                "title": title,
                "url": it.get("url", ""),
                "snippet": snippet,
                "source": it.get("source", ""),
                "published": (it.get("published") or "")[:10],
            }
        )

    guidance = _ROLE_REPORT_GUIDANCE.get(role, _ROLE_REPORT_GUIDANCE["web_research"])
    prompt = DETAILED_REPORT_PROMPT.format(
        role=role,
        query=query or "(none)",
        task=task or "(none)",
        guidance=guidance,
        items=json.dumps(numbered, indent=2, default=str),
    )

    try:
        response = llm.invoke(prompt)
        content = getattr(response, "content", "") or ""
        if isinstance(content, list):
            content = next(
                (p.get("text", "") for p in content if isinstance(p, dict) and p.get("text")),
                "",
            )
        text = (content or "").strip()
        # Strip accidental code fences.
        text = re.sub(r"^```(?:markdown|md)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
        # Sanity: must contain both required sections.
        if "## Findings" in text and "## Sources" in text:
            return text
        return fallback
    except Exception:
        return fallback


# --------------------------- runner factory --------------------------------


def _make_runner(role: str, llm) -> Callable[[dict[str, Any]], dict[str, Any]]:
    sources = ROLE_SOURCES.get(role, ["google-news"])

    def runner(payload: dict[str, Any]) -> dict[str, Any]:
        query = payload.get("query", "") or ""
        task = payload.get("task", "") or ""

        queries = _generate_queries(
            llm, role, query, task, sources, _DEFAULT_NUM_QUERIES
        )
        items = _collect(queries, sources, _DEFAULT_LIMIT, _DEFAULT_PERIOD)
        output = _write_short_report(llm, role, query, task, items)

        return {
            "worker_outputs": [
                {
                    "subtask_id": payload.get("subtask_id"),
                    "role": role,
                    "task": task,
                    "queries": queries,
                    "num_items": len(items),
                    "output": output,
                }
            ]
        }

    runner.__name__ = f"{role}_runner"
    return runner


# Role -> graph node name (kept stable to match graph.py wiring).
_ROLE_NODE_NAMES: dict[str, str] = {
    "data_collection": "data_collection_agent",
    "statistics": "statistics_agent",
    "citation": "citation_agent",
    "web_research": "web_research_agent",
    "latest_news_collection": "latest_news_collection_agent",
}


def build_role_runners(llm, tools: list | None = None) -> dict[str, Callable]:
    """Return ``node_name -> runner`` mapping for the workflow graph.

    The ``tools`` argument is accepted for backwards compatibility with the
    previous ReAct-agent-based implementation but is ignored: each runner
    calls :func:`fetch_trends` directly with deterministic queries.
    """
    return {
        node_name: _make_runner(role, llm)
        for role, node_name in _ROLE_NODE_NAMES.items()
    }
