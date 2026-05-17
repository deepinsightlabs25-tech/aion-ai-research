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
        if qtype not in ROLES_BY_TYPE:
            qtype = "summary"

        out = {
            "query_type": qtype,
            "classification_rationale": parsed.get("rationale", ""),
        }
        persist(db, state.get("task_id", ""), "classify", out)
        logger.info(f"[classifier] type={qtype} | {time.time() - t0:.1f}s")
        return out

    return node_classifier
