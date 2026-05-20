"""Report Finalizer node — enrich the report with LLM-emitted inline visuals.

The LLM is asked to embed Mermaid charts, GFM tables, and LaTeX ($$..$$)
formulas directly inside the Markdown report. No images are rendered on the
server; the frontend renders Mermaid + KaTeX in the browser.
"""

from __future__ import annotations

import json
import time
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from ..prompts import REPORT_FINALIZER_PROMPT
from ..state import WorkflowState
from ..helpers import safe_json_load, persist

logger = logging.getLogger(__name__)


def create_node_report_finalizer(llm, db):
    """Enrich the validated report with inline text-only visualizations."""

    def node_report_finalizer(state: WorkflowState):
        t0 = time.time()
        report = state.get("final_report") or state.get("draft_report") or ""
        aggregated = state.get("aggregated", {})
        task_id = state.get("task_id", "")

        if not report:
            persist(db, task_id, "report_finalizer", {"status": "NO_REPORT"})
            return {}

        prompt = REPORT_FINALIZER_PROMPT.format(
            report=report[:8000],
            aggregated=json.dumps(aggregated, indent=2, default=str)[:12000],
        )
        try:
            response = llm.invoke([
                SystemMessage(content=(
                    "You are a data-visualisation specialist. Return STRICT JSON only. "
                    "Embed Mermaid charts, GFM tables, and LaTeX formulas directly in the Markdown. "
                    "No images, no base64, no external file references."
                )),
                HumanMessage(content=prompt),
            ])
            parsed = safe_json_load(getattr(response, "content", "") or "")
        except Exception as e:
            persist(db, task_id, "report_finalizer",
                    {"status": "LLM_ERROR", "error": str(e)})
            return {"final_report": report}

        enhanced = (
            parsed.get("enhanced_report", report)
            if isinstance(parsed, dict) else report
        )

        persist(db, task_id, "report_finalizer", {
            "status": "SUCCESS",
            "length": len(enhanced),
        })
        logger.info(
            f"[report_finalizer] {len(enhanced)} chars | {time.time() - t0:.1f}s"
        )
        return {"final_report": enhanced}

    return node_report_finalizer
