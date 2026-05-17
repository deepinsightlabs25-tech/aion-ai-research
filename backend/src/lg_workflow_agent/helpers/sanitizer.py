"""Report sanitization — strips LLM tool/process meta-commentary leakage."""

from __future__ import annotations

import re


# Phrases that indicate the LLM is leaking tool/process meta-commentary.
# Any paragraph containing one of these (case-insensitive) is dropped from
# the final draft as a defensive post-processing step.
_LEAKAGE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bfetch_trends\b",
        r"\bthink_tool\b",
        r"\bsub[- ]?agent(s)?\b",
        r"\btool (limitation|failure|error|did not|was unable|could not)\b",
        r"\bdue to (tool|api|model) (limitation|constraint|issue|error)",
        r"\bcould not be (fully )?(gathered|obtained|retrieved|completed|determined)\b",
        r"\b(was|were) unable to (retrieve|gather|obtain|access)\b",
        r"\bno (data|results|information) (was|were) (returned|available|found)\b",
        r"\binsufficient data (was|is) available\b",
        r"\bas an ai\b",
        r"\bbased on the (information|data) provided\b",
        r"\bthe tool did not (yield|return|provide)\b",
        r"\bcomprehensive overview .* could not\b",
    )
)


def sanitize_report(text: str) -> str:
    """Strip paragraphs that leak tool/process meta-commentary.

    Acts as a defense-in-depth filter on top of the writer prompt. Removes any
    paragraph (separated by blank lines) that matches a known leakage pattern.
    Preserves headings and inline citations untouched.
    """
    if not text:
        return text
    paragraphs = re.split(r"(\n\s*\n)", text)  # keep separators
    out: list[str] = []
    for chunk in paragraphs:
        if chunk.strip().startswith(("#", "-", "*", "[", "|")):
            # Preserve headings, list items, references, and tables verbatim.
            out.append(chunk)
            continue
        if any(p.search(chunk) for p in _LEAKAGE_PATTERNS):
            continue
        out.append(chunk)
    cleaned = "".join(out)
    # Collapse 3+ blank lines that may result from removed paragraphs.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or text  # never return empty
