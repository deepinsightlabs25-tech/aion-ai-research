"""Report Finalizer node — enrich reports with auto-generated visualizations."""

from __future__ import annotations

import json
import re
import time
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from ..prompts import REPORT_FINALIZER_PROMPT
from ..state import WorkflowState
from ..helpers import safe_json_load, persist
from ..chart_generator import generate_charts_for_report

logger = logging.getLogger(__name__)


def create_node_report_finalizer(llm, db):
    """Enrich the validated report with auto-generated visualizations (charts, diagrams, formulas).

    This node:
    1. Sends the final report + aggregated data to the LLM to identify
       data points suitable for visualisation (charts, flows, formulas, diagrams).
    2. Renders visualizations via matplotlib into base64 PNG images.
    3. Embeds them as inline ``![caption](data:image/png;…)`` in the report.

    Supported visualization types:
    - Bar/Line/Area charts: for numerical data and trends
    - Flowcharts: for process flows and workflows
    - Architecture diagrams: for system comparisons
    - Heatmaps: for correlation and intensity data
    - Formulas: for mathematical relationships (LaTeX)
    - Matrix comparisons: for capability grids
    - Tables and stat cards: for key highlights
    """

    def node_report_finalizer(state: WorkflowState):
        t0 = time.time()
        report = state.get("final_report") or state.get("draft_report") or ""
        aggregated = state.get("aggregated", {})
        task_id = state.get("task_id", "")

        if not report:
            persist(db, task_id, "report_finalizer", {"status": "NO_REPORT"})
            return {}

        # Ask the LLM to produce chart specifications and an enhanced report
        # with {{CHART:<index>}} placement markers.
        prompt = REPORT_FINALIZER_PROMPT.format(
            report=report[:8000],  # Truncate very long reports
            aggregated=json.dumps(aggregated, indent=2, default=str)[:12000],
        )
        try:
            response = llm.invoke(
                [SystemMessage(content="You are a data-visualisation specialist. Return STRICT JSON only. Generate diverse, relevant visualizations: bar charts, line charts, flowcharts, architecture diagrams, formulas, heatmaps. Exclude metadata charts."),
                 HumanMessage(content=prompt)]
            )
            parsed = safe_json_load(getattr(response, "content", "") or "")
        except Exception as e:
            # If the LLM call fails, pass through the report unchanged.
            persist(db, task_id, "report_finalizer",
                    {"status": "LLM_ERROR", "error": str(e)})
            return {
                "final_report": report,
                "chart_specs": [],
                "report_images": [],
            }

        chart_specs = parsed.get("chart_specs", []) if isinstance(parsed, dict) else []
        enhanced_report = parsed.get("enhanced_report", report) if isinstance(parsed, dict) else report

        # Validate chart specs before rendering
        valid_charts = []
        for i, spec in enumerate(chart_specs):
            if not isinstance(spec, dict) or not spec.get("chart_type"):
                continue  # Skip invalid specs
            valid_charts.append(spec)

        # Render chart images with better error handling
        rendered_images: list[dict[str, str]] = []
        charts_failed = 0
        if valid_charts:
            rendered_images = generate_charts_for_report(valid_charts)
            charts_failed = len(valid_charts) - len(rendered_images)

        # Replace {{CHART:<index>}} markers with embedded images
        final_visual_report = enhanced_report
        for i, img in enumerate(rendered_images):
            marker = f"{{{{CHART:{i}}}}}"
            caption = img.get('caption', f'Visualization {i+1}')
            md_image = f"\n\n![{caption}]({img['data_uri']})\n\n"
            final_visual_report = final_visual_report.replace(marker, md_image)

        # Clean up any unreplaced markers (if chart rendering failed for some)
        final_visual_report = re.sub(r"\{\{CHART:\d+\}\}", "", final_visual_report)
        # Collapse excessive blank lines
        final_visual_report = re.sub(r"\n{3,}", "\n\n", final_visual_report).strip()

        # Persist visualization metrics
        persist(db, task_id, "report_finalizer", {
            "status": "SUCCESS",
            "charts_requested": len(valid_charts),
            "charts_rendered": len(rendered_images),
            "charts_failed": charts_failed,
            "chart_types": list(set(s.get("chart_type", "unknown") for s in valid_charts)),
        })

        logger.info(f"[report_finalizer] {len(chart_specs)} charts requested, {len(rendered_images)} rendered, {len(final_visual_report)} chars | {time.time() - t0:.1f}s")

        return {
            "final_report": final_visual_report,
            "chart_specs": valid_charts,
            "report_images": rendered_images,
        }

    return node_report_finalizer
