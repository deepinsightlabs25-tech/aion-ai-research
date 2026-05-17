"""Classifier node — classify the user query into a research mode."""

from __future__ import annotations

import time
import logging

from ..prompts import CLASSIFIER_PROMPT
from ..state import WorkflowState
from ..helpers import safe_json_load, persist
from ._constants import ROLES_BY_TYPE

logger = logging.getLogger(__name__)


def create_node_classifier(llm, db):
    """Classify the user query into a research mode."""

    def node_classifier(state: WorkflowState):
        t0 = time.time()
        prompt = CLASSIFIER_PROMPT.format(query=state["query"])
        response = llm.invoke(prompt)
        parsed = safe_json_load(getattr(response, "content", "") or "")

        qtype = parsed.get("query_type", "summary")
        ambiguous_reason = (parsed.get("ambiguous_reason") or "").strip()

        # Accept "ambiguous" as a valid terminal classification; otherwise
        # require it to be a known research type.
        if qtype == "ambiguous":
            if not ambiguous_reason:
                ambiguous_reason = (
                    "The query is too vague or unclear to produce a focused "
                    "research result. Please rephrase with a specific topic, "
                    "scope, and the kind of output you want (e.g. summary, "
                    "comparison, or deep-research report)."
                )
            out = {
                "query_type": "ambiguous",
                "is_ambiguous": True,
                "classification_rationale": parsed.get("rationale", "") or ambiguous_reason,
                "ambiguous_reason": ambiguous_reason,
            }
        else:
            if qtype not in ROLES_BY_TYPE:
                qtype = "summary"
            out = {
                "query_type": qtype,
                "is_ambiguous": False,
                "classification_rationale": parsed.get("rationale", ""),
                "ambiguous_reason": "",
            }

        persist(db, state.get("task_id", ""), "classify", out)
        logger.info(
            f"[classifier] type={out['query_type']} ambiguous={out['is_ambiguous']} | {time.time() - t0:.1f}s"
        )
        return out

    return node_classifier
