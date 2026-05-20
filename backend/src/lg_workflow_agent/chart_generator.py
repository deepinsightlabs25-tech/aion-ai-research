"""Deprecated stub.

The matplotlib-based chart pipeline has been replaced with LLM-native
Mermaid/KaTeX visualizations in the Markdown report and TikZ/pgfplots in
the LaTeX paper. This module is kept only to satisfy legacy imports
(notably ``src.pipeline.orchestrator._release_memory``).
"""

from __future__ import annotations

__all__ = ["generate_charts_for_report", "render_chart", "plt"]

# Sentinel so any legacy ``if chart_generator.plt is not None`` checks
# evaluate falsy without importing matplotlib.
plt = None


def generate_charts_for_report(chart_specs):  # noqa: D401 — legacy shim
    """Always returns an empty list. Charts are now embedded as text."""
    return []


def render_chart(spec):  # noqa: D401 — legacy shim
    """Always returns None. Charts are now embedded as text."""
    return None
