"""Cleanup node — persist final report and drop intermediates."""

from __future__ import annotations

from ..state import WorkflowState


def create_node_cleanup(db):
    """Persist the final report against the original query, then drop intermediates."""

    def node_cleanup(state: WorkflowState):
        final_report = state.get("final_report") or state.get("draft_report") or ""
        query = state.get("query", "")
        task_id = state.get("task_id", "")
        paper_latex = state.get("research_paper_latex")

        # Persist the finished report (and paper if available) keyed by the query.
        if db is not None and query and final_report:
            try:
                db.save_report(query, final_report, paper_latex=paper_latex)
            except Exception:
                pass

        # Drop intermediate per-task artifacts.
        if db is not None and task_id:
            try:
                db.cleanup_task_data(task_id)
            except Exception:
                pass

        if not state.get("final_report"):
            return {"final_report": final_report or "No Report Generated"}
        return {}

    return node_cleanup
