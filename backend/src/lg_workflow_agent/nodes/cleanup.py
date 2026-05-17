"""Cleanup node — persist final report and drop intermediates."""

from __future__ import annotations

from ..state import WorkflowState


def _build_ambiguous_report(query: str, reason: str) -> str:
    """Build a user-facing report explaining why an ambiguous query was rejected."""
    safe_query = query.strip() or "(empty query)"
    safe_reason = reason.strip() or (
        "The query is too vague or unclear to produce a focused research result."
    )
    return (
        "# Unable to Generate Research Result\n\n"
        f"**Your query:** {safe_query}\n\n"
        "## Why this query was not processed\n\n"
        f"{safe_reason}\n\n"
        "## How to get a useful result\n\n"
        "Please rephrase your query so it includes:\n"
        "- A **specific topic or entity** to research.\n"
        "- The **scope** (timeframe, domain, geography, etc.) where relevant.\n"
        "- The **kind of output** you want — for example a short summary, "
        "a comparison of two or more things, an explanatory blog, or a "
        "deep-research report with citations.\n\n"
        "_No sub-agents were run and no external sources were consulted "
        "for this query._\n"
    )


def create_node_cleanup(db):
    """Persist the final report against the original query, then drop intermediates."""

    def node_cleanup(state: WorkflowState):
        query = state.get("query", "")
        task_id = state.get("task_id", "")
        is_ambiguous = bool(state.get("is_ambiguous")) or state.get("query_type") == "ambiguous"

        if is_ambiguous:
            # Short-circuit path: classifier flagged the query as ambiguous,
            # so no research was performed. Produce an explanatory report
            # instead of an empty placeholder.
            final_report = _build_ambiguous_report(
                query, state.get("ambiguous_reason", "")
            )
            paper_latex = None
            paper_images = None
        else:
            final_report = state.get("final_report") or state.get("draft_report") or ""
            paper_latex = state.get("research_paper_latex")
            paper_images = state.get("research_paper_images") or None

        # Persist the finished report (and paper if available) keyed by the query.
        if db is not None and query and final_report:
            try:
                db.save_report(
                    query,
                    final_report,
                    paper_latex=paper_latex,
                    paper_images=paper_images if not is_ambiguous else None,
                )
            except Exception:
                pass

        # Drop intermediate per-task artifacts.
        if db is not None and task_id:
            try:
                db.cleanup_task_data(task_id)
            except Exception:
                pass

        if is_ambiguous:
            return {"final_report": final_report}

        if not state.get("final_report"):
            return {"final_report": final_report or "No Report Generated"}
        return {}

    return node_cleanup
