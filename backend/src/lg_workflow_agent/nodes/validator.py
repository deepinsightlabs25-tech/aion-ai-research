"""Validator node — validate references via URL reachability and LLM relevance."""

from __future__ import annotations

import json
import time
import logging
from typing import Any

from ..prompts import VALIDATOR_PROMPT
from ..state import WorkflowState
from ..helpers import safe_json_load, persist, build_reference_snippets
from ..tools import extract_urls, validate_urls
from ._constants import MAX_REWRITES

logger = logging.getLogger(__name__)


def create_node_validator(llm, db):
    """Validate references on TWO axes:

    1. URL reachability — HEAD/GET against each URL (broken links rejected).
    2. LLM relevance — does the URL+snippet support the query intention/subtasks?
    Any reference failing either check goes into ``invalid_references`` and
    triggers a writer rewrite (capped by ``MAX_REWRITES``).
    """

    def node_validator(state: WorkflowState):
        t0 = time.time()
        draft = state.get("draft_report", "")
        aggregated = state.get("aggregated", {}) or {}
        query = state.get("query", "")
        query_type = state.get("query_type", "")
        subtasks = state.get("subtasks", []) or []

        references = build_reference_snippets(aggregated, draft)

        # If the aggregator produced no structured refs, fall back to URLs in the draft.
        if not references:
            for i, url in enumerate(extract_urls(draft), start=1):
                references.append(
                    {"id": i, "url": url, "title": "", "snippet": draft[:400]}
                )

        iterations = state.get("rewrite_iterations", 0)
        task_id = state.get("task_id", "")

        if not references:
            persist(db, task_id, "validation", {"status": "VALID", "checked": 0})
            logger.info(f"[validator] VALID (no refs) | {time.time() - t0:.1f}s")
            return {
                "final_report": draft,
                "validation_feedback": "VALID (no references)",
                "invalid_references": [],
            }

        # ---- 1. URL reachability ------------------------------------------------
        all_urls = [r["url"] for r in references if r.get("url")]
        reach = validate_urls(all_urls) if all_urls else {}
        broken = [u for u, ok in reach.items() if not ok]

        # Only ask the LLM to evaluate references whose URL is reachable; broken
        # ones are already invalid.
        live_refs = [r for r in references if reach.get(r.get("url", ""), False)]

        # ---- 2. LLM relevance ---------------------------------------------------
        irrelevant: list[str] = []
        verdict_log: list[dict[str, Any]] = []
        llm_error: str | None = None

        if live_refs:
            subtasks_rendered = "\n".join(
                f"- [{st.get('role', '?')}] {st.get('task', '')}" for st in subtasks
            ) or "(none)"
            refs_rendered = json.dumps(live_refs, indent=2, default=str)[:8000]
            prompt = VALIDATOR_PROMPT.format(
                query=query,
                query_type=query_type,
                subtasks=subtasks_rendered,
                references=refs_rendered,
            )
            try:
                response = llm.invoke(prompt)
                parsed = safe_json_load(getattr(response, "content", "") or "")
                verdicts = parsed.get("verdicts", []) if isinstance(parsed, dict) else []
                for v in verdicts:
                    if not isinstance(v, dict):
                        continue
                    verdict_log.append(v)
                    if v.get("relevant") is False and v.get("url"):
                        irrelevant.append(v["url"])
            except Exception as exc:
                llm_error = str(exc)

        # Combined invalid set (broken + irrelevant), de-duplicated, order-preserving.
        seen: set[str] = set()
        invalid: list[str] = []
        for u in broken + irrelevant:
            if u and u not in seen:
                seen.add(u)
                invalid.append(u)

        # ---- Decision -----------------------------------------------------------
        elapsed = time.time() - t0
        if not invalid:
            persist(db, task_id, "validation", {
                "status": "VALID",
                "checked": len(references),
                "verdicts": verdict_log,
                "llm_error": llm_error,
            })
            logger.info(f"[validator] VALID — checked {len(references)} refs, {len(broken)} broken | {elapsed:.1f}s")
            return {
                "final_report": draft,
                "validation_feedback": "VALID" + (
                    f" (validator LLM error: {llm_error})" if llm_error else ""
                ),
                "invalid_references": [],
            }

        if iterations >= MAX_REWRITES:
            cleaned = draft
            for u in invalid:
                cleaned = cleaned.replace(u, "[invalid link removed]")
            persist(db, task_id, "validation", {
                "status": "FORCED_FINISH",
                "broken": broken,
                "irrelevant": irrelevant,
                "verdicts": verdict_log,
            })
            logger.info(f"[validator] FORCED_FINISH after {iterations} rewrites — {len(broken)} broken, {len(irrelevant)} irrelevant | {elapsed:.1f}s")
            return {
                "final_report": cleaned,
                "validation_feedback": f"FORCED_FINISH after {iterations} rewrites",
                "invalid_references": [],
            }

        persist(db, task_id, "validation", {
            "status": "INVALID_REFS",
            "broken": broken,
            "irrelevant": irrelevant,
            "verdicts": verdict_log,
        })
        logger.info(f"[validator] INVALID — {len(broken)} broken, {len(irrelevant)} irrelevant → rewrite #{iterations + 1} | {elapsed:.1f}s")
        return {
            "validation_feedback": (
                f"INVALID_REFS: {len(broken)} broken, {len(irrelevant)} irrelevant"
            ),
            "invalid_references": invalid,
            "rewrite_iterations": iterations + 1,
        }

    return node_validator


def create_validation_route():
    def route(state: WorkflowState):
        return "valid" if state.get("validation_feedback") == "VALID" or state.get("final_report") else "rewrite"
    return route
