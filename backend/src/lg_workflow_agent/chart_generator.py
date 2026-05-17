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
import textwrap
from typing import Any

__all__ = ["generate_charts_for_report", "render_chart"]

# ──────────────────────── Theme ────────────────────────────────────────────
# Publication-quality light theme (IEEE/Elsevier-style).
_BG = "#ffffff"        # figure & axes background
_FG = "#1a1a1a"        # primary text/ink
_MUTED = "#4a4a4a"     # secondary text
_RULE = "#b8b8b8"      # axis spines / borders
_GRID = "#dcdcdc"      # gridlines
_HEADER_BG = "#e9eef5" # table header band (very light blue-gray)
_BAND_BG = "#f5f7fa"   # table zebra band
_CARD_BG = "#ffffff"   # stat-card fill
_CARD_EDGE = "#c8ced8" # stat-card border

# Colorblind-safe muted palette (based on Tableau 10 / Color Universal Design).
_ACCENT_COLORS = [
    "#3B5B8C",  # navy blue
    "#A24A4A",  # muted brick red
    "#5B7F4F",  # sage green
    "#B07A2A",  # ochre / dark gold
    "#6B5B95",  # dusty purple
    "#4F8593",  # slate teal
    "#8A6F47",  # warm taupe
    "#7A7A7A",  # neutral gray
]

# ── Lazy-loaded matplotlib references (saves ~50 MB until first chart) ─────
plt = None
np = None
mticker = None
mpatches = None
FancyBboxPatch = None
FancyArrowPatch = None


def _ensure_matplotlib():
    """Import matplotlib and numpy on first use to save startup memory."""
    global plt, np, mticker, mpatches, FancyBboxPatch, FancyArrowPatch
    if plt is not None:
        return

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt
    import matplotlib.ticker as _mticker
    import matplotlib.patches as _mpatches
    from matplotlib.patches import FancyBboxPatch as _FBP, FancyArrowPatch as _FAP
    import numpy as _np

    plt = _plt
    np = _np
    mticker = _mticker
    mpatches = _mpatches
    FancyBboxPatch = _FBP
    FancyArrowPatch = _FAP

    plt.rcParams.update(
        {
            "figure.facecolor": _BG,
            "axes.facecolor": _BG,
            "axes.edgecolor": _RULE,
            "axes.linewidth": 0.8,
            "axes.labelcolor": _FG,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlepad": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": _GRID,
            "grid.linewidth": 0.6,
            "grid.alpha": 1.0,
            "grid.linestyle": "-",
            "text.color": _FG,
            "xtick.color": _FG,
            "ytick.color": _FG,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "legend.facecolor": _BG,
            "legend.edgecolor": _RULE,
            "legend.frameon": True,
            "legend.framealpha": 1.0,
            "legend.fontsize": 9,
            "font.family": "serif",
            "font.serif": ["DejaVu Serif", "Times New Roman", "Liberation Serif", "serif"],
            "font.size": 10,
            "figure.dpi": 150,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            "savefig.facecolor": _BG,
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

    fig, ax = plt.subplots(figsize=(7.2, max(3.6, len(labels) * 0.45) if horizontal else 4.4))
    # Single muted colour for single-series bar charts looks more academic
    # than rainbow per-bar colouring.
    primary = _ACCENT_COLORS[0]

    if horizontal:
        y_pos = np.arange(len(labels))
        ax.barh(y_pos, values, color=primary, height=0.62, edgecolor="white", linewidth=0.5)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=9)
        if xlabel:
            ax.set_xlabel(xlabel, fontsize=10)
        ax.invert_yaxis()
        ax.xaxis.grid(True)
        ax.yaxis.grid(False)
    else:
        x_pos = np.arange(len(labels))
        ax.bar(x_pos, values, color=primary, width=0.62, edgecolor="white", linewidth=0.5)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, fontsize=9, rotation=25, ha="right")
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=10)
        ax.yaxis.grid(True)
        ax.xaxis.grid(False)

    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", pad=10)

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

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    markers = ["o", "s", "^", "D", "v", "P", "X", "*"]
    linestyles = ["-", "--", "-.", ":"]
    for i, s in enumerate(series):
        color = _ACCENT_COLORS[i % len(_ACCENT_COLORS)]
        ax.plot(
            s.get("x", list(range(len(s.get("y", []))))),
            s.get("y", []),
            marker=markers[i % len(markers)],
            linestyle=linestyles[i % len(linestyles)],
            color=color,
            linewidth=1.6,
            markersize=5,
            markerfacecolor=color,
            markeredgecolor="white",
            markeredgewidth=0.6,
            label=s.get("name", f"Series {i + 1}"),
        )
    if len(series) > 1:
        ax.legend(loc="best")
    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_pie_chart(spec: dict) -> str:
    labels = spec.get("labels", [])
    values = spec.get("values", [])
    title = spec.get("title", "")

    if not labels or not values:
        return ""

    colors = [_ACCENT_COLORS[i % len(_ACCENT_COLORS)] for i in range(len(labels))]
    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        colors=colors,
        startangle=140,
        pctdistance=0.78,
        wedgeprops={"linewidth": 1.0, "edgecolor": "white"},
        textprops={"color": _FG, "fontsize": 9},
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_color("white")
        at.set_fontweight("bold")
    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", pad=14)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _wrap_cell(text: str, width: int) -> str:
    """Wrap long cell text so it fits within a column without overlapping."""
    text = str(text) if text is not None else ""
    if not text:
        return ""
    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        if not paragraph:
            lines.append("")
            continue
        wrapped = textwrap.wrap(
            paragraph,
            width=width,
            break_long_words=True,
            break_on_hyphens=True,
        ) or [""]
        lines.extend(wrapped)
    return "\n".join(lines)


def _make_comparison_table(spec: dict) -> str:
    """Render a comparison table as a styled image (avoids markdown table limitations)."""
    headers = spec.get("headers", [])
    rows = spec.get("rows", [])
    title = spec.get("title", "")

    if not headers or not rows:
        return ""

    n_cols = len(headers)
    # Pick a per-column wrap width based on the number of columns so the
    # rendered image stays readable. Fewer columns = wider wrap.
    if n_cols <= 2:
        wrap_width = 48
        col_in = 3.6
    elif n_cols == 3:
        wrap_width = 34
        col_in = 3.0
    elif n_cols == 4:
        wrap_width = 26
        col_in = 2.6
    else:
        wrap_width = 20
        col_in = 2.2

    wrapped_headers = [_wrap_cell(h, wrap_width) for h in headers]
    wrapped_rows = [[_wrap_cell(c, wrap_width) for c in row] for row in rows]

    # Estimate row heights from the maximum number of wrapped lines per row.
    def _line_count(s: str) -> int:
        return max(1, s.count("\n") + 1)

    header_lines = max(_line_count(h) for h in wrapped_headers)
    row_lines = [max(_line_count(c) for c in row) for row in wrapped_rows]

    # ~0.32 inches per text line + padding.
    fig_h = max(3.0, header_lines * 0.36 + sum(l * 0.32 for l in row_lines) + 1.0)
    fig_w = max(8.0, n_cols * col_in)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")

    table = ax.table(
        cellText=wrapped_rows,
        colLabels=wrapped_headers,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)

    total_lines = header_lines + sum(row_lines)
    # Pixel height available for the table area (figure minus title pad).
    # Set each cell height proportional to its line count so wrapped text
    # doesn't overlap into the next row.
    cells = table.get_celld()
    base_unit = 1.0 / max(1, total_lines)
    for (row_idx, col_idx), cell in cells.items():
        cell.set_edgecolor(_RULE)
        cell.set_linewidth(0.6)
        # Padding inside the cell so text doesn't touch borders.
        cell.PAD = 0.05
        if row_idx == 0:
            cell.set_facecolor(_HEADER_BG)
            cell.set_text_props(color=_FG, fontweight="bold")
            cell.set_height(base_unit * header_lines * 1.4)
        else:
            cell.set_facecolor(_BG if row_idx % 2 == 1 else _BAND_BG)
            cell.set_text_props(color=_FG)
            cell.set_height(base_unit * row_lines[row_idx - 1] * 1.4)

    if title:
        fig.suptitle(title, fontsize=12, fontweight="bold", color=_FG, y=0.99)
        fig.tight_layout(rect=[0, 0, 1, 0.94])
    else:
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
        accent = _ACCENT_COLORS[i % len(_ACCENT_COLORS)]
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # white card with thin border + accent top rule
        rect = plt.Rectangle((0.05, 0.05), 0.9, 0.9, facecolor=_CARD_BG,
                              edgecolor=_CARD_EDGE, linewidth=1.0, transform=ax.transAxes,
                              clip_on=False, zorder=1)
        ax.add_patch(rect)
        top_rule = plt.Rectangle((0.05, 0.88), 0.9, 0.07, facecolor=accent,
                                  edgecolor="none", transform=ax.transAxes,
                                  clip_on=False, zorder=2)
        ax.add_patch(top_rule)

        value_str = str(m.get("value", ""))
        unit = m.get("unit", "")
        label = m.get("label", "")
        ax.text(0.5, 0.55, f"{value_str}{unit}", transform=ax.transAxes,
                ha="center", va="center", fontsize=20, fontweight="bold", color=_FG,
                zorder=3)
        ax.text(0.5, 0.22, label, transform=ax.transAxes,
                ha="center", va="center", fontsize=9, color=_MUTED, zorder=3)

    fig.suptitle(title, fontsize=12, fontweight="bold", color=_FG, y=0.98)
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

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    x_data = series[0].get("x", list(range(len(series[0].get("y", [])))))

    for i, s in enumerate(series):
        color = _ACCENT_COLORS[i % len(_ACCENT_COLORS)]
        ax.fill_between(
            x_data,
            s.get("y", []),
            alpha=0.25,
            color=color,
            label=s.get("name", f"Series {i + 1}"),
        )
        ax.plot(
            x_data,
            s.get("y", []),
            color=color,
            linewidth=1.6,
            marker="o",
            markersize=4,
        )

    ax.legend(loc="best", framealpha=1.0)
    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _make_heatmap(spec: dict) -> str:
    """Render a heatmap for correlation or intensity data."""
    data = spec.get("data", [])  # 2D list
    labels_x = spec.get("labels_x", [])
    labels_y = spec.get("labels_y", [])
    title = spec.get("title", "")
    cmap_name = spec.get("colormap", "Blues")

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
    # Wrap each step's text so it fits the box width (~28 chars per line).
    wrap_width = 28
    wrapped = [_wrap_cell(s.get("text", f"Step {i+1}"), wrap_width)
               for i, s in enumerate(steps)]
    line_counts = [max(1, t.count("\n") + 1) for t in wrapped]

    # Per-step vertical slot scales with wrapped line count to prevent
    # overflow into adjacent boxes/arrows.
    slot_heights = [1.0 + 0.35 * (lc - 1) for lc in line_counts]
    total_h = sum(slot_heights)

    fig_h = max(5.0, total_h * 1.1 + 0.8)
    fig, ax = plt.subplots(figsize=(8.0, fig_h))
    ax.set_xlim(-1, 3)
    ax.set_ylim(-0.3, total_h + 0.6)
    ax.axis("off")

    # Compute box centres from the top down.
    centres: list[float] = []
    cursor = total_h
    for h in slot_heights:
        cursor -= h
        centres.append(cursor + h / 2.0)

    box_half_widths = 0.85  # x: 0.15 -> 1.85
    for i, (step, text, centre, slot_h, lc) in enumerate(
        zip(steps, wrapped, centres, slot_heights, line_counts)
    ):
        accent = step.get("color", _ACCENT_COLORS[i % len(_ACCENT_COLORS)])
        box_h = 0.5 + 0.32 * (lc - 1)

        box = FancyBboxPatch(
            (1.0 - box_half_widths, centre - box_h / 2.0),
            box_half_widths * 2.0, box_h,
            boxstyle="round,pad=0.08",
            facecolor="#f5f7fa",
            edgecolor=accent,
            linewidth=1.4,
        )
        ax.add_patch(box)

        ax.text(1, centre, text, ha="center", va="center",
                fontsize=9, fontweight="bold", color=_FG,
                linespacing=1.15)

        # Arrow from this box's bottom to the next box's top.
        if i < n_steps - 1:
            next_centre = centres[i + 1]
            next_lc = line_counts[i + 1]
            next_box_h = 0.5 + 0.32 * (next_lc - 1)
            arrow_top = centre - box_h / 2.0 - 0.02
            arrow_bottom = next_centre + next_box_h / 2.0 + 0.02
            if arrow_top > arrow_bottom:
                arrow = FancyArrowPatch(
                    (1, arrow_top), (1, arrow_bottom),
                    arrowstyle="-|>",
                    mutation_scale=14,
                    linewidth=1.2,
                    color=_MUTED,
                )
                ax.add_patch(arrow)

    if title:
        ax.text(1, total_h + 0.35, title, ha="center", va="bottom",
                fontsize=12, fontweight="bold", color=_FG)

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
        accent = comp.get("color", _ACCENT_COLORS[idx % len(_ACCENT_COLORS)])

        wrapped_name = _wrap_cell(name, 18)
        wrapped_type = _wrap_cell(comp_type, 22)
        name_lines = wrapped_name.count("\n") + 1
        # Grow box height a little when the name wraps to >1 line.
        box_h = 0.6 + 0.18 * max(0, name_lines - 1)

        box = FancyBboxPatch(
            (x - 0.42, y - box_h / 2.0), 0.84, box_h,
            boxstyle="round,pad=0.04",
            facecolor="#f5f7fa",
            edgecolor=accent,
            linewidth=1.4,
        )
        ax.add_patch(box)

        ax.text(x, y + 0.10, wrapped_name, ha="center", va="center",
                fontsize=8.5, fontweight="bold", color=_FG, linespacing=1.1)
        ax.text(x, y - box_h / 2.0 + 0.10, f"({wrapped_type})",
                ha="center", va="center",
                fontsize=7, color=_MUTED, style="italic", linespacing=1.1)

    if title:
        ax.text(cols / 2, rows + 0.2, title, ha="center", va="bottom",
                fontsize=12, fontweight="bold", color=_FG)

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
                bbox=dict(boxstyle="round,pad=0.8", facecolor="#f5f7fa",
                          edgecolor=_RULE, linewidth=1.0))
    except Exception:
        ax.text(0.5, 0.6, formula, ha="center", va="center",
                fontsize=16, transform=ax.transAxes, color=_FG)

    if title:
        ax.text(0.5, 0.95, title, ha="center", va="top",
                fontsize=12, fontweight="bold", transform=ax.transAxes, color=_FG)

    if description:
        ax.text(0.5, 0.15, description, ha="center", va="center",
                fontsize=10, transform=ax.transAxes, color=_MUTED, style="italic", wrap=True)
    
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
                fontsize=10, fontweight="bold", color=_FG)

    # Items and scores
    for i, item in enumerate(items):
        name = item.get("name", f"Item {i+1}")
        scores = item.get("scores", [0] * len(categories))

        ax.text(-0.3, len(items) - 1 - i, name, ha="right", va="center",
                fontsize=9, fontweight="bold", color=_FG)

        for j, score in enumerate(scores):
            score = min(100, max(0, float(score)))
            # Light blue ramp for academic look (instead of red-yellow-green).
            color = plt.cm.Blues(0.25 + 0.55 * (score / 100.0))

            rect = plt.Rectangle((j - 0.36, len(items) - 1.36 - i), 0.72, 0.72,
                                  facecolor=color, edgecolor=_RULE, linewidth=0.8)
            ax.add_patch(rect)

            # Pick text color for readability against the cell fill.
            txt_color = "white" if score >= 65 else _FG
            ax.text(j, len(items) - 1 - i, f"{int(score)}", ha="center", va="center",
                    fontsize=9, fontweight="bold", color=txt_color)

    if title:
        ax.text(len(categories) / 2, len(items) + 0.5, title, ha="center", va="bottom",
                fontsize=12, fontweight="bold", color=_FG)
    
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
    _ensure_matplotlib()
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
    # Release any matplotlib state still held by pyplot to free memory
    # between queries (each figure can retain several MB of buffers).
    if plt is not None:
        try:
            plt.close("all")
        except Exception:
            pass
    return results
