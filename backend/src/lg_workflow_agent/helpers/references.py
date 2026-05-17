"""Reference snippet builder for validation scoring."""

from __future__ import annotations

from typing import Any


def build_reference_snippets(
    aggregated: dict[str, Any],
    draft: str,
    radius: int = 220,
) -> list[dict[str, Any]]:
    """For each reference build {id, url, title, snippet} for relevance scoring.

    The snippet is the surrounding text of the first occurrence of the inline
    [n] citation in the report; falls back to the section content or the
    reference title if no inline marker is found.
    """
    refs = aggregated.get("references", []) or []
    sections = aggregated.get("sections", []) or []
    full_text = draft or "\n\n".join(
        s.get("content", "") for s in sections if isinstance(s, dict)
    )

    out: list[dict[str, Any]] = []
    for r in refs:
        if not isinstance(r, dict):
            continue
        rid = r.get("id")
        url = r.get("url", "")
        title = r.get("title", "")
        snippet = ""
        if rid is not None and full_text:
            marker = f"[{rid}]"
            idx = full_text.find(marker)
            if idx != -1:
                start = max(0, idx - radius)
                end = min(len(full_text), idx + len(marker) + radius)
                snippet = full_text[start:end].strip()
        if not snippet:
            # Fallback: any section that mentions the URL or title.
            for s in sections:
                content = s.get("content", "") if isinstance(s, dict) else ""
                if (url and url in content) or (title and title in content):
                    snippet = content[:radius * 2]
                    break
        if not snippet:
            snippet = title or url
        out.append(
            {
                "id": rid,
                "url": url,
                "title": title,
                "snippet": snippet,
            }
        )
    return out
