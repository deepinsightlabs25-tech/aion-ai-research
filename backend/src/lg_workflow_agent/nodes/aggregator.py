"""Aggregator node — consolidate sub-agent outputs into a structured object."""

from __future__ import annotations

import json
import time
import logging

from ..prompts import AGGREGATOR_PROMPT
from ..state import WorkflowState
from ..helpers import safe_json_load, persist

logger = logging.getLogger(__name__)


def create_node_aggregator(llm, db):
    """Consolidate sub-agent outputs into a structured aggregated object."""

    def node_aggregator(state: WorkflowState):
        t0 = time.time()
        outputs = state.get("worker_outputs", [])
        rendered = "\n\n".join(
            f"### {o.get('role', '?')} :: {o.get('subtask_id', '?')}\n"
            f"Task: {o.get('task', '')}\n\n{o.get('output', '')}"
            for o in outputs
        ) or "(no outputs)"

        prompt = AGGREGATOR_PROMPT.format(
            query=state.get("query", ""),
            query_type=state.get("query_type", ""),
            outputs=rendered,
        )
        response = llm.invoke(prompt)
        parsed = safe_json_load(getattr(response, "content", "") or "")

        # Sanity defaults.
        if not isinstance(parsed, dict) or "sections" not in parsed:
            parsed = {
                "metadata": {
                    "query": state.get("query", ""),
                    "query_type": state.get("query_type", ""),
                    "num_sources": 0,
                },
                "sections": [{"title": "Findings", "content": rendered}],
                "references": [],
            }

        persist(db, state.get("task_id", ""), "aggregation", parsed)
        logger.info(f"[aggregator] {len(outputs)} outputs → {len(parsed.get('sections', []))} sections | {time.time() - t0:.1f}s")
        return {"aggregated": parsed}

    return node_aggregator
