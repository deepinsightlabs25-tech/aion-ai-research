"""Chart and graph generation for rich visual reports.

Generates matplotlib-based charts as base64-encoded PNG images suitable for
embedding directly in Markdown reports via data-URI ``![…](data:image/png;…)``
syntax.  All charts use a dark professional theme for consistency.

Supports:
- Traditional charts: bar, line, pie, area
- Comparison: comparison_table, heatmap
- Highlight: stat_card
- Flow diagrams: flowchart, workflow
- Mathematical: formula
- Infographic: architecture_diagram
"""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless backend — must be set before pyplot import
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

__all__ = ["generate_charts_for_report", "render_chart"]

# ──────────────────────── Theme ────────────────────────────────────────────
_BG = "#0f1117"
_FG = "#e0e0e0"
_ACCENT_COLORS = [
    "#6C63FF",  # vivid indigo
    "#00D4AA",  # teal
    "#FF6B6B",  # coral
    "#FFD93D",  # gold
    "#4ECDC4",  # cyan
    "#FF8C42",  # orange
    "#A855F7",  # purple
    "#38BDF8",  # sky-blue
]

plt.rcParams.update(
    {
        "figure.facecolor": _BG,
        "axes.facecolor": "#1a1d29",
        "axes.edgecolor": "#2d3148",
        "axes.labelcolor": _FG,
        "axes.grid": True,
        "grid.color": "#2d3148",
        "grid.alpha": 0.5,
        "text.color": _FG,
        "xtick.color": _FG,
        "ytick.color": _FG,
        "legend.facecolor": "#1a1d29",
        "legend.edgecolor": "#2d3148",
        "font.size": 11,
        "figure.dpi": 96,
    }
)


# ──────────────────────── Low-level renderers ──────────────────────────────


def _fig_to_base64(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.getvalue()).decode()
    buf.close()
    return b64


def _make_bar_chart(spec: dict) -> str:
    """Vertical or horizontal bar chart."""
    labels = spec.get("labels", [])
    values = spec.get("values", [])
    title = spec.get("title", "")
    xlabel = spec.get("xlabel", "")
    ylabel = spec.get("ylabel", "")
    horizontal = spec.get("horizontal", False)

    if not labels or not values:
        return ""

    fig, ax = plt.subplots(figsize=(8, max(4, len(labels) * 0.5) if horizontal else 5))
    colors = [_ACCENT_COLORS[i % len(_ACCENT_COLORS)] for i in range(len(labels))]

    if horizontal:
        y_pos = np.arange(len(labels))
        ax.barh(y_pos, values, color=colors, height=0.6, edgecolor="none")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=10)
        if xlabel:
            ax.set_xlabel(xlabel)
        ax.invert_yaxis()
    else:
        x_pos = np.arange(len(labels))
        ax.bar(x_pos, values, color=colors, width=0.6, edgecolor="none")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, fontsize=10, rotation=30, ha="right")
        if ylabel:
            ax.set_ylabel(ylabel)

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)

    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_line_chart(spec: dict) -> str:
    """Single or multi-series line chart."""
    title = spec.get("title", "")
    xlabel = spec.get("xlabel", "")
    ylabel = spec.get("ylabel", "")
    series = spec.get("series", [])  # [{name, x, y}]

    if not series:
        return ""

    fig, ax = plt.subplots(figsize=(8, 5))
    for i, s in enumerate(series):
        color = _ACCENT_COLORS[i % len(_ACCENT_COLORS)]
        ax.plot(
            s.get("x", list(range(len(s.get("y", []))))),
            s.get("y", []),
            marker="o",
            color=color,
            linewidth=2.5,
            markersize=6,
            label=s.get("name", f"Series {i + 1}"),
        )
    if len(series) > 1:
        ax.legend()
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_pie_chart(spec: dict) -> str:
    labels = spec.get("labels", [])
    values = spec.get("values", [])
    title = spec.get("title", "")

    if not labels or not values:
        return ""

    colors = [_ACCENT_COLORS[i % len(_ACCENT_COLORS)] for i in range(len(labels))]
    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        colors=colors,
        startangle=140,
        pctdistance=0.8,
        textprops={"color": _FG, "fontsize": 10},
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_color("#ffffff")
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=16)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_comparison_table(spec: dict) -> str:
    """Render a comparison table as a styled image (avoids markdown table limitations)."""
    headers = spec.get("headers", [])
    rows = spec.get("rows", [])
    title = spec.get("title", "")

    if not headers or not rows:
        return ""

    fig, ax = plt.subplots(figsize=(max(8, len(headers) * 2.2), max(3, len(rows) * 0.65 + 1.2)))
    ax.axis("off")

    cell_text = [[str(c) for c in row] for row in rows]
    table = ax.table(
        cellText=cell_text,
        colLabels=headers,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.8)

    # Style cells
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#2d3148")
        if row == 0:
            cell.set_facecolor("#6C63FF")
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor("#1a1d29" if row % 2 == 1 else "#20243a")
            cell.set_text_props(color=_FG)

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20, color=_FG)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_stat_card(spec: dict) -> str:
    """Render key metrics as a highlight card image."""
    metrics = spec.get("metrics", [])  # [{label, value, unit?}]
    title = spec.get("title", "Key Statistics")

    if not metrics:
        return ""

    n = len(metrics)
    fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 2.8))
    if n == 1:
        axes = [axes]

    for i, (ax, m) in enumerate(zip(axes, metrics)):
        color = _ACCENT_COLORS[i % len(_ACCENT_COLORS)]
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # background card
        rect = plt.Rectangle((0.05, 0.05), 0.9, 0.9, facecolor="#1a1d29",
                              edgecolor=color, linewidth=2, transform=ax.transAxes,
                              clip_on=False, zorder=1)
        ax.add_patch(rect)

        value_str = str(m.get("value", ""))
        unit = m.get("unit", "")
        label = m.get("label", "")
        ax.text(0.5, 0.62, f"{value_str}{unit}", transform=ax.transAxes,
                ha="center", va="center", fontsize=22, fontweight="bold", color=color,
                zorder=2)
        ax.text(0.5, 0.28, label, transform=ax.transAxes,
                ha="center", va="center", fontsize=10, color=_FG, zorder=2)

    fig.suptitle(title, fontsize=13, fontweight="bold", color=_FG, y=0.97)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    return _fig_to_base64(fig)


def _make_area_chart(spec: dict) -> str:
    """Render a stacked area chart for trends."""
    title = spec.get("title", "")
    xlabel = spec.get("xlabel", "")
    ylabel = spec.get("ylabel", "")
    series = spec.get("series", [])  # [{name, x, y}]

    if not series:
        return ""

    fig, ax = plt.subplots(figsize=(9, 5.5))
    x_data = series[0].get("x", list(range(len(series[0].get("y", [])))))
    
    for i, s in enumerate(series):
        color = _ACCENT_COLORS[i % len(_ACCENT_COLORS)]
        ax.fill_between(
            x_data,
            s.get("y", []),
            alpha=0.4,
            color=color,
            label=s.get("name", f"Series {i + 1}"),
        )
        ax.plot(
            x_data,
            s.get("y", []),
            color=color,
            linewidth=2.5,
            marker="o",
            markersize=5,
        )
    
    ax.legend(loc="upper left", framealpha=0.95)
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_heatmap(spec: dict) -> str:
    """Render a heatmap for correlation or intensity data."""
    data = spec.get("data", [])  # 2D list
    labels_x = spec.get("labels_x", [])
    labels_y = spec.get("labels_y", [])
    title = spec.get("title", "")
    cmap_name = spec.get("colormap", "viridis")

    if not data or not labels_x or not labels_y:
        return ""

    fig, ax = plt.subplots(figsize=(max(8, len(labels_x) * 0.8), max(6, len(labels_y) * 0.8)))
    data_array = np.array(data)
    
    im = ax.imshow(data_array, cmap=cmap_name, aspect="auto", origin="lower")
    ax.set_xticks(np.arange(len(labels_x)))
    ax.set_yticks(np.arange(len(labels_y)))
    ax.set_xticklabels(labels_x, fontsize=9, rotation=45, ha="right")
    ax.set_yticklabels(labels_y, fontsize=9)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Intensity", rotation=270, labelpad=15)
    
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_flowchart(spec: dict) -> str:
    """Render a simple flowchart with boxes and arrows."""
    steps = spec.get("steps", [])  # [{"text": "Step 1", "color": "#color"}]
    title = spec.get("title", "Process Flow")

    if not steps:
        return ""

    n_steps = len(steps)
    fig, ax = plt.subplots(figsize=(10, max(6, n_steps * 1.2)))
    ax.set_xlim(-1, 3)
    ax.set_ylim(-0.5, n_steps)
    ax.axis("off")

    for i, step in enumerate(steps):
        y_pos = n_steps - 1 - i
        text = step.get("text", f"Step {i+1}")
        color = step.get("color", _ACCENT_COLORS[i % len(_ACCENT_COLORS)])
        
        # Draw box
        box = FancyBboxPatch(
            (0.2, y_pos - 0.35), 1.6, 0.6,
            boxstyle="round,pad=0.1",
            facecolor=color,
            edgecolor=_FG,
            linewidth=2,
            alpha=0.7,
        )
        ax.add_patch(box)
        
        # Add text
        ax.text(1, y_pos, text, ha="center", va="center", 
                fontsize=11, fontweight="bold", color="white", wrap=True)
        
        # Draw arrow to next step
        if i < n_steps - 1:
            arrow = FancyArrowPatch(
                (1, y_pos - 0.4), (1, y_pos - 0.65),
                arrowstyle="->",
                mutation_scale=25,
                linewidth=2,
                color=_FG,
            )
            ax.add_patch(arrow)

    if title:
        ax.text(1, n_steps + 0.3, title, ha="center", va="bottom",
                fontsize=14, fontweight="bold", color=_FG)
    
    return _fig_to_base64(fig)


def _make_architecture_diagram(spec: dict) -> str:
    """Render an architecture/component diagram."""
    components = spec.get("components", [])  # [{"name": "...", "type": "..."}]
    title = spec.get("title", "System Architecture")

    if not components:
        return ""

    n_components = len(components)
    cols = min(4, max(2, int(np.ceil(np.sqrt(n_components)))))
    rows = int(np.ceil(n_components / cols))
    
    fig, ax = plt.subplots(figsize=(cols * 3, rows * 2.5))
    ax.set_xlim(-0.5, cols)
    ax.set_ylim(-0.5, rows)
    ax.axis("off")

    for idx, comp in enumerate(components):
        row = rows - 1 - (idx // cols)
        col = idx % cols
        x, y = col + 0.5, row + 0.5
        
        name = comp.get("name", f"Component {idx+1}")
        comp_type = comp.get("type", "module")
        color = comp.get("color", _ACCENT_COLORS[idx % len(_ACCENT_COLORS)])
        
        # Draw component box
        box = FancyBboxPatch(
            (x - 0.35, y - 0.3), 0.7, 0.6,
            boxstyle="round,pad=0.05",
            facecolor=color,
            edgecolor=_FG,
            linewidth=2,
            alpha=0.8,
        )
        ax.add_patch(box)
        
        # Add labels
        ax.text(x, y + 0.15, name, ha="center", va="center",
                fontsize=9, fontweight="bold", color="white")
        ax.text(x, y - 0.1, f"({comp_type})", ha="center", va="center",
                fontsize=7, color="white", style="italic")

    if title:
        ax.text(cols / 2, rows + 0.2, title, ha="center", va="bottom",
                fontsize=14, fontweight="bold", color=_FG)
    
    return _fig_to_base64(fig)


def _make_formula(spec: dict) -> str:
    """Render a mathematical formula or equation using LaTeX."""
    formula = spec.get("formula", "")
    title = spec.get("title", "")
    description = spec.get("description", "")

    if not formula:
        return ""

    fig, ax = plt.subplots(figsize=(10, 3))
    ax.axis("off")
    
    # Render LaTeX formula
    try:
        ax.text(0.5, 0.6, f"${formula}$", ha="center", va="center",
                fontsize=20, transform=ax.transAxes, color=_FG,
                bbox=dict(boxstyle="round,pad=0.8", facecolor="#1a1d29",
                          edgecolor=_ACCENT_COLORS[0], linewidth=2))
    except Exception:
        ax.text(0.5, 0.6, formula, ha="center", va="center",
                fontsize=16, transform=ax.transAxes, color=_FG)
    
    if title:
        ax.text(0.5, 0.95, title, ha="center", va="top",
                fontsize=12, fontweight="bold", transform=ax.transAxes, color=_FG)
    
    if description:
        ax.text(0.5, 0.15, description, ha="center", va="center",
                fontsize=10, transform=ax.transAxes, color=_FG, style="italic", wrap=True)
    
    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_matrix_comparison(spec: dict) -> str:
    """Render a capability/feature matrix as a visual grid."""
    items = spec.get("items", [])  # [{"name": "Item", "score": 0-100}]
    categories = spec.get("categories", [])  # ["Speed", "Accuracy", "Cost"]
    title = spec.get("title", "")

    if not items or not categories:
        return ""

    fig, ax = plt.subplots(figsize=(max(8, len(categories) * 1.5), max(5, len(items) * 0.8)))
    ax.set_xlim(-0.5, len(categories))
    ax.set_ylim(-0.5, len(items))
    ax.axis("off")

    # Header
    for j, cat in enumerate(categories):
        ax.text(j, len(items), cat, ha="center", va="center",
                fontsize=11, fontweight="bold", color=_ACCENT_COLORS[j % len(_ACCENT_COLORS)])

    # Items and scores
    for i, item in enumerate(items):
        name = item.get("name", f"Item {i+1}")
        scores = item.get("scores", [0] * len(categories))
        
        ax.text(-0.3, len(items) - 1 - i, name, ha="right", va="center",
                fontsize=10, fontweight="bold", color=_FG)
        
        for j, score in enumerate(scores):
            score = min(100, max(0, float(score)))
            color_intensity = score / 100.0
            color = plt.cm.RdYlGn(color_intensity)
            
            # Draw cell
            rect = plt.Rectangle((j - 0.35, len(items) - 1.35 - i), 0.7, 0.7,
                                  facecolor=color, edgecolor=_FG, linewidth=1)
            ax.add_patch(rect)
            
            # Add score
            ax.text(j, len(items) - 1 - i, f"{int(score)}", ha="center", va="center",
                    fontsize=9, fontweight="bold", color="black")

    if title:
        ax.text(len(categories) / 2, len(items) + 0.5, title, ha="center", va="bottom",
                fontsize=14, fontweight="bold", color=_FG)
    
    return _fig_to_base64(fig)


# ──────────────────────── Dispatch ────────────────────────────────────────

_RENDERERS = {
    "bar": _make_bar_chart,
    "horizontal_bar": lambda s: _make_bar_chart({**s, "horizontal": True}),
    "line": _make_line_chart,
    "pie": _make_pie_chart,
    "comparison_table": _make_comparison_table,
    "stat_card": _make_stat_card,
    "area": _make_area_chart,
    "heatmap": _make_heatmap,
    "flowchart": _make_flowchart,
    "architecture": _make_architecture_diagram,
    "formula": _make_formula,
    "matrix": _make_matrix_comparison,
}


def render_chart(spec: dict) -> str | None:
    """Render a single chart spec and return a base64 data-URI string.

    Returns ``None`` if the spec is invalid or the chart type is unknown.
    """
    chart_type = spec.get("chart_type", "")
    renderer = _RENDERERS.get(chart_type)
    if renderer is None:
        return None
    try:
        b64 = renderer(spec)
        if not b64:
            return None
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def generate_charts_for_report(chart_specs: list[dict]) -> list[dict[str, str]]:
    """Generate all charts from a list of specs.

    Returns a list of ``{"caption": "…", "data_uri": "data:image/png;…"}`` dicts.
    Only successfully rendered charts are included.
    """
    results: list[dict[str, str]] = []
    for spec in chart_specs:
        uri = render_chart(spec)
        if uri:
            results.append({
                "caption": spec.get("caption", spec.get("title", "Chart")),
                "data_uri": uri,
            })
    return results
