"""Writer node — produce the final markdown report from aggregated structure."""

from __future__ import annotations

import json
import time
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from ..prompts import REWRITE_NOTE_TEMPLATE, WRITER_PROMPT
from ..state import WorkflowState
from ..helpers import persist, sanitize_report

logger = logging.getLogger(__name__)


def create_node_writer(llm, db):
    """Produce the final markdown report from the aggregated structure."""

    def node_writer(state: WorkflowState):
        t0 = time.time()
        aggregated = state.get("aggregated", {})
        invalid_refs = state.get("invalid_references", [])
        rewrite_note = ""
        if invalid_refs:
            rewrite_note = REWRITE_NOTE_TEMPLATE.format(
                invalid_refs="\n".join(f"- {u}" for u in invalid_refs)
            )

        prompt = WRITER_PROMPT.format(
            aggregated=json.dumps(aggregated, indent=2, default=str),
            rewrite_note=rewrite_note,
        )
        response = llm.invoke(
            [SystemMessage(content="You write professional markdown reports."),
             HumanMessage(content=prompt)]
        )
        draft = response.content if isinstance(response.content, str) else str(response.content)
        draft = sanitize_report(draft)

        persist(db, state.get("task_id", ""), "draft", draft)
        logger.info(f"[writer] {len(draft)} chars (rewrite #{state.get('rewrite_iterations', 0)}) | {time.time() - t0:.1f}s")
        # Reset invalid refs after applying them in a rewrite pass.
        return {"draft_report": draft, "invalid_references": []}

    return node_writer
