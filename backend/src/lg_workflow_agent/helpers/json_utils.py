"""JSON parsing utilities for LLM responses."""

from __future__ import annotations

import json
import re


def safe_json_load(text: str) -> dict:
    """Load JSON from an LLM response, tolerating ```json fences."""
    if not text:
        return {}
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        # Try to extract first JSON object
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
        return {}
