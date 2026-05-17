"""Sample run & test script for the lg_workflow_agent.

Usage (from the backend/ directory with the venv activated):

    # --- Full pipeline runs ---
    python -m src.lg_workflow_agent.run_sample
    python -m src.lg_workflow_agent.run_sample "your custom query here"
    python -m src.lg_workflow_agent.run_sample --stream "your custom query"

    # --- Test individual nodes ---
    python -m src.lg_workflow_agent.run_sample --test-nodes
    python -m src.lg_workflow_agent.run_sample --test-nodes classifier task_generator

    # --- Test research paper generator ---
    python -m src.lg_workflow_agent.run_sample --test-paper

    # --- Test chart / visualisation renderer ---
    python -m src.lg_workflow_agent.run_sample --test-charts

    # --- Run all tests ---
    python -m src.lg_workflow_agent.run_sample --test-all

Requires environment variables:
    GOOGLE_API_KEY        (for Gemini — needed by node tests that call the LLM)
    DEEP_AGENT_MODEL      (optional, defaults to gemini-2.5-flash)
    QDRANT_URL/API_KEY    (optional; falls back to in-memory Qdrant)
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

# Ensure backend/ is on sys.path when run as a script (not as -m).
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from src.lg_workflow_agent import WorkflowAgent  # noqa: E402
from src.lg_workflow_agent.nodes import (  # noqa: E402
    create_node_classifier,
    create_node_task_generator,
    create_node_aggregator,
    create_node_writer,
    create_node_validator,
    create_node_report_finalizer,
    create_node_paper_writer,
    create_node_cleanup,
    create_assign_workers,
)
from src.lg_workflow_agent.chart_generator import (  # noqa: E402
    generate_charts_for_report,
    render_chart,
)
from src.lg_workflow_agent.paper_formatter import (  # noqa: E402
    clean_latex,
    compile_latex_to_pdf,
    extract_paper_metadata,
    validate_latex,
)
from src.lg_workflow_agent.state import WorkflowState  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

REPORTS_DIR = BACKEND_ROOT / "reports"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_llm():
    """Build the Gemini LLM used by node tests."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    model_name = os.environ.get("DEEP_AGENT_MODEL", "gemini-2.5-flash")
    if model_name.startswith("google_genai:"):
        model_name = model_name.split(":", 1)[1]
    return ChatGoogleGenerativeAI(model=model_name, temperature=0.0)


def _header(title: str) -> None:
    width = max(60, len(title) + 6)
    print(f"\n{'=' * width}")
    print(f"   {title}")
    print(f"{'=' * width}\n")


def _result(name: str, passed: bool, detail: str = "", elapsed: float = 0.0) -> bool:
    icon = "PASS" if passed else "FAIL"
    t = f" ({elapsed:.1f}s)" if elapsed else ""
    print(f"  [{icon}] {name}{t}")
    if detail:
        for line in detail.strip().split("\n"):
            print(f"         {line}")
    return passed


def save_report(report: str, query: str) -> Path:
    """Save *report* to a timestamped markdown file under reports/."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = query[:40].strip().replace(" ", "_").replace("/", "-")
    filename = f"report_{timestamp}_{slug}.md"
    path = REPORTS_DIR / filename
    path.write_text(f"# Research Report\n\n**Query:** {query}\n\n---\n\n{report}\n", encoding="utf-8")
    print(f"\n[Report saved -> {path}]")
    return path


DEFAULT_QUERY = (
    "Compare LangGraph vs CrewAI vs AutoGen for building multi-agent research "
    "assistants in 2026 — focus on orchestration model, streaming, and tool use."
)

# ─────────────────────────────────────────────────────────────────────────────
# Seed data for isolated node tests
# ─────────────────────────────────────────────────────────────────────────────

SEED_QUERY = "Compare LangGraph vs CrewAI for building AI agents in 2026"
SEED_TASK_ID = "test-run-001"

SEED_STATE_BASE: WorkflowState = {
    "query": SEED_QUERY,
    "task_id": SEED_TASK_ID,
    "messages": [],
    "rewrite_iterations": 0,
    "invalid_references": [],
}

SEED_SUBTASKS = [
    {"id": "s1", "role": "web_research", "task": "Compare LangGraph vs CrewAI architecture", "status": "pending"},
    {"id": "s2", "role": "latest_news_collection", "task": "Latest news on LangGraph and CrewAI in 2026", "status": "pending"},
]

SEED_WORKER_OUTPUTS = [
    {
        "subtask_id": "s1",
        "role": "web_research",
        "task": "Compare LangGraph vs CrewAI architecture",
        "output": (
            "LangGraph uses a graph-based orchestration model with nodes and edges. "
            "It supports streaming, checkpointing, and human-in-the-loop via interrupt nodes. "
            "CrewAI uses a role-based crew metaphor with agents, tasks, and processes. "
            "LangGraph is lower-level and more flexible; CrewAI is higher-level and opinionated.\n\n"
            "References:\n"
            "- [1] https://langchain-ai.github.io/langgraph/\n"
            "- [2] https://docs.crewai.com/"
        ),
    },
    {
        "subtask_id": "s2",
        "role": "latest_news_collection",
        "task": "Latest news on LangGraph and CrewAI in 2026",
        "output": (
            "In 2026 LangGraph released v0.4 with native multi-agent support. "
            "CrewAI launched CrewAI Enterprise with managed deployments. "
            "Both frameworks saw strong adoption for research assistant use cases.\n\n"
            "References:\n"
            "- [3] https://blog.langchain.dev/\n"
            "- [4] https://www.crewai.com/blog"
        ),
    },
]

SEED_AGGREGATED = {
    "metadata": {"query": SEED_QUERY, "query_type": "comparative", "num_sources": 4},
    "sections": [
        {
            "title": "Architecture Comparison",
            "content": (
                "LangGraph uses graph-based orchestration with nodes and edges [1]. "
                "CrewAI uses role-based crews with agents and tasks [2]."
            ),
        },
        {
            "title": "Recent Developments",
            "content": (
                "LangGraph v0.4 added native multi-agent support [3]. "
                "CrewAI launched Enterprise tier [4]."
            ),
        },
        {
            "title": "Streaming & Tool Use",
            "content": (
                "LangGraph supports per-node streaming and checkpoint-based resumption. "
                "CrewAI introduced tool delegation in v3."
            ),
        },
    ],
    "references": [
        {"id": 1, "url": "https://langchain-ai.github.io/langgraph/", "title": "LangGraph Docs"},
        {"id": 2, "url": "https://docs.crewai.com/", "title": "CrewAI Docs"},
        {"id": 3, "url": "https://blog.langchain.dev/", "title": "LangChain Blog"},
        {"id": 4, "url": "https://www.crewai.com/blog", "title": "CrewAI Blog"},
    ],
}

SEED_DRAFT_REPORT = """\
# LangGraph vs CrewAI: A Comparative Analysis (2026)

## Architecture Comparison

LangGraph employs a graph-based orchestration model where workflows are defined as nodes connected by edges [1]. \
CrewAI takes a higher-level, role-based approach with agents organized into crews and tasks [2].

## Recent Developments

LangGraph v0.4 introduced native multi-agent support with improved streaming [3]. \
CrewAI launched its Enterprise tier with managed deployments and enhanced tooling [4].

## Streaming & Tool Use

LangGraph supports per-node streaming and checkpoint-based resumption for long-running workflows. \
CrewAI introduced tool delegation capabilities in v3, allowing agents to share tools across crews.

## References

- [1] LangGraph Documentation — https://langchain-ai.github.io/langgraph/
- [2] CrewAI Documentation — https://docs.crewai.com/
- [3] LangChain Blog — https://blog.langchain.dev/
- [4] CrewAI Blog — https://www.crewai.com/blog
"""

SAMPLE_LATEX = r"""\documentclass[12pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb}
\usepackage{hyperref}
\usepackage{geometry}
\geometry{margin=1in}

\title{LangGraph vs CrewAI: A Comparative Study}
\author{AI Research Agent}
\date{2026}

\begin{abstract}
This paper compares LangGraph and CrewAI, two leading multi-agent orchestration frameworks.
We analyse their architecture, streaming capabilities, and tool-use paradigms.
\end{abstract}

\begin{document}
\maketitle

\section{Introduction}
Multi-agent systems have become a cornerstone of modern AI applications \cite{langchain2024}.
This paper evaluates two prominent frameworks: LangGraph and CrewAI.

\section{Architecture}
LangGraph uses a directed-graph model where each node represents a processing step \cite{langgraph2025}.
CrewAI adopts a role-based metaphor with agents, tasks, and processes \cite{crewai2025}.

\section{Streaming}
LangGraph supports per-node streaming via async generators, enabling real-time UI updates.
CrewAI added streaming support in version 3 with callback-based event propagation.

\section{Tool Use}
Both frameworks support LangChain-compatible tools. LangGraph binds tools at the node level,
while CrewAI allows tool delegation between agents within a crew.

\section{Conclusion}
LangGraph offers finer-grained control for complex workflows, while CrewAI provides
a simpler developer experience for standard multi-agent patterns.

\begin{thebibliography}{9}
\bibitem{langchain2024} LangChain Team, ``LangChain Documentation,'' 2024.
\bibitem{langgraph2025} LangChain AI, ``LangGraph: Multi-Agent Orchestration,'' 2025.
\bibitem{crewai2025} CrewAI, ``CrewAI Documentation,'' 2025.
\end{thebibliography}

\end{document}
"""

# ─────────────────────────────────────────────────────────────────────────────
# Node tests
# ─────────────────────────────────────────────────────────────────────────────

def test_classifier(llm) -> bool:
    """Test the classifier node: expects a valid query_type."""
    t0 = time.time()
    try:
        node_fn = create_node_classifier(llm, db=None)
        result = node_fn(SEED_STATE_BASE)
        qtype = result.get("query_type", "")
        rationale = result.get("classification_rationale", "")
        valid_types = {"blog", "comparative", "deep_research", "summary"}
        ok = qtype in valid_types
        return _result(
            "classifier",
            ok,
            f"query_type={qtype!r}, rationale={rationale[:80]}",
            time.time() - t0,
        )
    except Exception as exc:
        return _result("classifier", False, f"Exception: {exc}", time.time() - t0)


def test_task_generator(llm) -> bool:
    """Test the task_generator node: expects subtasks and worker_payloads."""
    t0 = time.time()
    try:
        node_fn = create_node_task_generator(llm, db=None)
        state = {**SEED_STATE_BASE, "query_type": "comparative"}
        result = node_fn(state)
        subtasks = result.get("subtasks", [])
        payloads = result.get("worker_payloads", [])
        ok = len(subtasks) > 0 and len(payloads) > 0
        roles = [s.get("role") for s in subtasks]
        return _result(
            "task_generator",
            ok,
            f"{len(subtasks)} subtasks, roles={roles}",
            time.time() - t0,
        )
    except Exception as exc:
        return _result("task_generator", False, f"Exception: {exc}", time.time() - t0)


def test_assign_workers() -> bool:
    """Test the fan-out routing: expects Send objects for each payload."""
    t0 = time.time()
    try:
        assign_fn = create_assign_workers()
        state: WorkflowState = {
            **SEED_STATE_BASE,
            "worker_payloads": [
                {"role": "web_research", "subtask_id": "s1", "task": "test", "query": SEED_QUERY, "task_id": SEED_TASK_ID},
                {"role": "latest_news_collection", "subtask_id": "s2", "task": "test", "query": SEED_QUERY, "task_id": SEED_TASK_ID},
            ],
        }
        sends = assign_fn(state)
        ok = len(sends) == 2
        targets = [s.node for s in sends]
        return _result(
            "assign_workers (fan-out)",
            ok,
            f"Sends to: {targets}",
            time.time() - t0,
        )
    except Exception as exc:
        return _result("assign_workers (fan-out)", False, f"Exception: {exc}", time.time() - t0)


def test_aggregator(llm) -> bool:
    """Test the aggregator node: expects structured aggregated output."""
    t0 = time.time()
    try:
        node_fn = create_node_aggregator(llm, db=None)
        state: WorkflowState = {
            **SEED_STATE_BASE,
            "query_type": "comparative",
            "worker_outputs": SEED_WORKER_OUTPUTS,
        }
        result = node_fn(state)
        agg = result.get("aggregated", {})
        sections = agg.get("sections", [])
        ok = isinstance(agg, dict) and len(sections) > 0
        return _result(
            "aggregator",
            ok,
            f"{len(sections)} sections, keys={sorted(agg.keys())}",
            time.time() - t0,
        )
    except Exception as exc:
        return _result("aggregator", False, f"Exception: {exc}", time.time() - t0)


def test_writer(llm) -> bool:
    """Test the writer node: expects a non-empty draft_report."""
    t0 = time.time()
    try:
        node_fn = create_node_writer(llm, db=None)
        state: WorkflowState = {
            **SEED_STATE_BASE,
            "aggregated": SEED_AGGREGATED,
        }
        result = node_fn(state)
        draft = result.get("draft_report", "")
        ok = len(draft) > 100 and "#" in draft
        return _result(
            "writer",
            ok,
            f"{len(draft)} chars, has headings={'#' in draft}",
            time.time() - t0,
        )
    except Exception as exc:
        return _result("writer", False, f"Exception: {exc}", time.time() - t0)


def test_validator(llm) -> bool:
    """Test the validator node: expects validation_feedback."""
    t0 = time.time()
    try:
        node_fn = create_node_validator(llm, db=None)
        state: WorkflowState = {
            **SEED_STATE_BASE,
            "query_type": "comparative",
            "subtasks": SEED_SUBTASKS,
            "aggregated": SEED_AGGREGATED,
            "draft_report": SEED_DRAFT_REPORT,
        }
        result = node_fn(state)
        feedback = result.get("validation_feedback", "")
        ok = bool(feedback)
        has_final = bool(result.get("final_report"))
        return _result(
            "validator",
            ok,
            f"feedback={feedback!r}, final_report={'yes' if has_final else 'no'}",
            time.time() - t0,
        )
    except Exception as exc:
        return _result("validator", False, f"Exception: {exc}", time.time() - t0)


def test_report_finalizer(llm) -> bool:
    """Test the report_finalizer node: expects chart specs and enriched report."""
    t0 = time.time()
    try:
        node_fn = create_node_report_finalizer(llm, db=None)
        state: WorkflowState = {
            **SEED_STATE_BASE,
            "final_report": SEED_DRAFT_REPORT,
            "aggregated": SEED_AGGREGATED,
        }
        result = node_fn(state)
        charts = result.get("chart_specs", [])
        images = result.get("report_images", [])
        final = result.get("final_report", "")
        ok = len(final) > 100
        return _result(
            "report_finalizer",
            ok,
            f"{len(charts)} chart specs, {len(images)} images rendered, {len(final)} chars",
            time.time() - t0,
        )
    except Exception as exc:
        return _result("report_finalizer", False, f"Exception: {exc}", time.time() - t0)


def test_paper_writer(llm) -> bool:
    """Test the paper_writer node: expects LaTeX output for deep_research."""
    t0 = time.time()
    try:
        node_fn = create_node_paper_writer(llm, db=None)
        state: WorkflowState = {
            **SEED_STATE_BASE,
            "query_type": "deep_research",
            "final_report": SEED_DRAFT_REPORT,
            "aggregated": SEED_AGGREGATED,
        }
        result = node_fn(state)
        latex = result.get("research_paper_latex", "")
        meta = result.get("research_paper_metadata", {})
        pdf_b64 = result.get("research_paper_pdf_base64")
        ok = len(latex) > 200 and r"\documentclass" in latex
        return _result(
            "paper_writer",
            ok,
            (
                f"{len(latex)} chars LaTeX, "
                f"title={meta.get('title', '?')!r}, "
                f"sections={meta.get('sections', [])}, "
                f"pdf={'yes' if pdf_b64 else 'no'}"
            ),
            time.time() - t0,
        )
    except Exception as exc:
        return _result("paper_writer", False, f"Exception: {exc}", time.time() - t0)


def test_paper_writer_skip(llm) -> bool:
    """Test that paper_writer is a no-op for non-deep_research queries."""
    t0 = time.time()
    try:
        node_fn = create_node_paper_writer(llm, db=None)
        state: WorkflowState = {
            **SEED_STATE_BASE,
            "query_type": "comparative",
            "final_report": SEED_DRAFT_REPORT,
            "aggregated": SEED_AGGREGATED,
        }
        result = node_fn(state)
        ok = result == {}
        return _result(
            "paper_writer (skip non-deep)",
            ok,
            f"returned {result!r}",
            time.time() - t0,
        )
    except Exception as exc:
        return _result("paper_writer (skip non-deep)", False, f"Exception: {exc}", time.time() - t0)


def test_cleanup() -> bool:
    """Test the cleanup node: expects it to run without error."""
    t0 = time.time()
    try:
        node_fn = create_node_cleanup(db=None)
        state: WorkflowState = {
            **SEED_STATE_BASE,
            "final_report": SEED_DRAFT_REPORT,
        }
        result = node_fn(state)
        ok = isinstance(result, dict)
        return _result("cleanup", ok, f"returned keys={sorted(result.keys())}", time.time() - t0)
    except Exception as exc:
        return _result("cleanup", False, f"Exception: {exc}", time.time() - t0)


# Map of test-name -> (needs_llm, test_func)
NODE_TESTS: dict[str, tuple[bool, Any]] = {
    "classifier":        (True,  test_classifier),
    "task_generator":    (True,  test_task_generator),
    "assign_workers":    (False, test_assign_workers),
    "aggregator":        (True,  test_aggregator),
    "writer":            (True,  test_writer),
    "validator":         (True,  test_validator),
    "report_finalizer":  (True,  test_report_finalizer),
    "paper_writer":      (True,  test_paper_writer),
    "paper_writer_skip": (True,  test_paper_writer_skip),
    "cleanup":           (False, test_cleanup),
}


def run_node_tests(selected: list[str] | None = None) -> None:
    """Run individual node tests. If *selected* is empty, runs all."""
    _header("Node Tests")

    names = selected if selected else list(NODE_TESTS.keys())
    unknown = [n for n in names if n not in NODE_TESTS]
    if unknown:
        print(f"  Unknown node(s): {unknown}")
        print(f"  Available: {list(NODE_TESTS.keys())}")
        return

    llm = None
    needs_llm = any(NODE_TESTS[n][0] for n in names)
    if needs_llm:
        print("  Building LLM for node tests...\n")
        llm = _get_llm()

    passed = 0
    failed = 0
    for name in names:
        needs, fn = NODE_TESTS[name]
        try:
            ok = fn(llm) if needs else fn()
        except Exception:
            ok = _result(name, False, traceback.format_exc())
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n  Summary: {passed} passed, {failed} failed, {passed + failed} total")

# ─────────────────────────────────────────────────────────────────────────────
# Chart / visualisation tests
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_CHART_SPECS: list[dict[str, Any]] = [
    {
        "chart_type": "bar",
        "title": "Framework Popularity (GitHub Stars)",
        "caption": "GitHub stars comparison",
        "labels": ["LangGraph", "CrewAI", "AutoGen"],
        "values": [18500, 22000, 31000],
        "ylabel": "Stars",
    },
    {
        "chart_type": "line",
        "title": "Monthly Downloads Trend",
        "caption": "PyPI downloads over time",
        "series": [
            {"name": "LangGraph", "x": ["Jan", "Feb", "Mar", "Apr"], "y": [120, 180, 250, 310]},
            {"name": "CrewAI", "x": ["Jan", "Feb", "Mar", "Apr"], "y": [90, 140, 200, 280]},
        ],
        "xlabel": "Month",
        "ylabel": "Downloads (K)",
    },
    {
        "chart_type": "pie",
        "title": "Market Share 2026",
        "caption": "Framework market share",
        "labels": ["LangGraph", "CrewAI", "AutoGen", "Other"],
        "values": [35, 28, 22, 15],
    },
    {
        "chart_type": "comparison_table",
        "title": "Feature Comparison",
        "caption": "Feature comparison table",
        "headers": ["Feature", "LangGraph", "CrewAI"],
        "rows": [
            ["Streaming", "Yes", "Yes (v3+)"],
            ["Checkpointing", "Yes", "No"],
            ["Human-in-loop", "Yes", "Limited"],
        ],
    },
    {
        "chart_type": "stat_card",
        "title": "Key Metrics",
        "caption": "Key metrics overview",
        "metrics": [
            {"label": "Frameworks Compared", "value": 3},
            {"label": "Sources Analysed", "value": 24},
            {"label": "Papers Referenced", "value": 8},
        ],
    },
]


def run_chart_tests() -> None:
    """Test the chart/visualisation renderer with each supported type."""
    _header("Chart & Visualisation Tests")

    passed = 0
    failed = 0

    # Test individual chart types
    for spec in SAMPLE_CHART_SPECS:
        ctype = spec["chart_type"]
        t0 = time.time()
        try:
            uri = render_chart(spec)
            ok = uri is not None and uri.startswith("data:image/png;base64,")
            size = len(uri) if uri else 0
            if _result(f"render: {ctype}", ok, f"data_uri size={size}", time.time() - t0):
                passed += 1
            else:
                failed += 1
        except Exception as exc:
            _result(f"render: {ctype}", False, f"Exception: {exc}", time.time() - t0)
            failed += 1

    # Test unknown chart type (should return None gracefully)
    t0 = time.time()
    uri = render_chart({"chart_type": "unknown_type"})
    ok = uri is None
    if _result("render: unknown_type (graceful fail)", ok, f"returned {uri!r}", time.time() - t0):
        passed += 1
    else:
        failed += 1

    # Test batch generation
    t0 = time.time()
    results = generate_charts_for_report(SAMPLE_CHART_SPECS)
    ok = len(results) == len(SAMPLE_CHART_SPECS)
    if _result(
        "generate_charts_for_report (batch)",
        ok,
        f"{len(results)}/{len(SAMPLE_CHART_SPECS)} rendered, "
        f"captions={[r['caption'] for r in results]}",
        time.time() - t0,
    ):
        passed += 1
    else:
        failed += 1

    print(f"\n  Summary: {passed} passed, {failed} failed, {passed + failed} total")

# ─────────────────────────────────────────────────────────────────────────────
# Paper formatter tests
# ─────────────────────────────────────────────────────────────────────────────

def run_paper_tests() -> None:
    """Test the research paper formatter: validation, cleaning, metadata, compilation."""
    _header("Research Paper Formatter Tests")

    passed = 0
    failed = 0

    # 1. validate_latex with valid LaTeX
    t0 = time.time()
    is_valid, issues = validate_latex(SAMPLE_LATEX)
    ok = is_valid and len(issues) == 0
    if _result("validate_latex (valid sample)", ok, f"valid={is_valid}, issues={issues}", time.time() - t0):
        passed += 1
    else:
        failed += 1

    # 2. validate_latex with broken LaTeX
    t0 = time.time()
    broken = r"\begin{document}\section{Oops}\end{document}"
    is_valid, issues = validate_latex(broken)
    ok = not is_valid and len(issues) > 0
    if _result("validate_latex (broken sample)", ok, f"valid={is_valid}, issues={issues[:3]}", time.time() - t0):
        passed += 1
    else:
        failed += 1

    # 3. validate_latex with empty input
    t0 = time.time()
    is_valid, issues = validate_latex("")
    ok = not is_valid
    if _result("validate_latex (empty)", ok, f"valid={is_valid}, issues={issues}", time.time() - t0):
        passed += 1
    else:
        failed += 1

    # 4. clean_latex strips markdown fences
    t0 = time.time()
    fenced = f"```latex\n{SAMPLE_LATEX}\n```"
    cleaned = clean_latex(fenced)
    ok = cleaned.startswith(r"\documentclass") and "```" not in cleaned
    if _result("clean_latex (strip fences)", ok, f"starts_with=\\documentclass, len={len(cleaned)}", time.time() - t0):
        passed += 1
    else:
        failed += 1

    # 5. clean_latex fixes markdown bold inside LaTeX
    t0 = time.time()
    with_md = SAMPLE_LATEX.replace("Multi-agent systems", "**Multi-agent systems**")
    cleaned = clean_latex(with_md)
    ok = r"\textbf{Multi-agent systems}" in cleaned and "**" not in cleaned
    if _result("clean_latex (markdown bold -> textbf)", ok, "", time.time() - t0):
        passed += 1
    else:
        failed += 1

    # 6. clean_latex removes \\includegraphics
    t0 = time.time()
    with_figure = SAMPLE_LATEX.replace(
        r"\section{Introduction}",
        r"\section{Introduction}" + "\n\\includegraphics[width=0.5\\textwidth]{fig.png}\n",
    )
    cleaned = clean_latex(with_figure)
    ok = r"\includegraphics" not in cleaned
    if _result("clean_latex (strip includegraphics)", ok, "", time.time() - t0):
        passed += 1
    else:
        failed += 1

    # 7. extract_paper_metadata
    t0 = time.time()
    meta = extract_paper_metadata(SAMPLE_LATEX)
    ok = (
        meta["title"] == "LangGraph vs CrewAI: A Comparative Study"
        and len(meta["sections"]) >= 4
        and meta["word_count"] > 50
        and "multi-agent" in meta["abstract"].lower()
    )
    if _result(
        "extract_paper_metadata",
        ok,
        f"title={meta['title']!r}, sections={meta['sections']}, words={meta['word_count']}",
        time.time() - t0,
    ):
        passed += 1
    else:
        failed += 1

    # 8. compile_latex_to_pdf (may fail if TinyTeX unavailable — still informative)
    t0 = time.time()
    pdf_bytes, errors = compile_latex_to_pdf(SAMPLE_LATEX)
    if pdf_bytes is not None:
        ok = len(pdf_bytes) > 100
        _result(
            "compile_latex_to_pdf",
            ok,
            f"PDF={len(pdf_bytes)} bytes",
            time.time() - t0,
        )
        passed += 1
    else:
        # Not a failure if TinyTeX isn't installed — just informational
        _result(
            "compile_latex_to_pdf (TinyTeX not available)",
            True,
            f"Skipped — errors: {errors}",
            time.time() - t0,
        )
        passed += 1

    print(f"\n  Summary: {passed} passed, {failed} failed, {passed + failed} total")

# ─────────────────────────────────────────────────────────────────────────────
# Full pipeline runs (sync / stream)
# ─────────────────────────────────────────────────────────────────────────────

def run_sync(query: str) -> None:
    print(f"\n=== Building WorkflowAgent ===")
    agent = WorkflowAgent()
    agent.build()
    print(f"Agent ready. Running query:\n  {query}\n")

    print("=== Invoking workflow (sync) ===")
    report = agent.invoke(query)

    print("\n=== FINAL REPORT ===\n")
    print(report)
    print("\n=== END REPORT ===")
    save_report(report, query)


async def run_stream(query: str) -> None:
    print(f"\n=== Building WorkflowAgent (streaming) ===")
    agent = WorkflowAgent()
    agent.build()
    print(f"Agent ready. Streaming query:\n  {query}\n")

    final_report = ""
    chart_count = 0
    image_count = 0
    async for event in agent.astream(query):
        step = event.get("step", "?")
        data = event.get("data", {})

        # Compact per-step trace (avoid dumping huge base64 blobs)
        keys = sorted(k for k in data.keys() if k != "messages")
        # Summarise data — truncate any field with base64 content
        display_data = {}
        for k in keys:
            v = data[k]
            if isinstance(v, str) and len(v) > 2000:
                display_data[k] = f"<{len(v)} chars>"
            elif isinstance(v, list) and k in ("report_images", "chart_specs"):
                display_data[k] = f"<{len(v)} items>"
            else:
                display_data[k] = v
        print(f"~~~~~~~~~~~~~~~~~~~~~~ [{step}] keys={keys}")
        print(f" | data : {json.dumps(display_data, indent=2, default=str)}\n")

        if data.get("final_report"):
            final_report = data["final_report"]
        elif data.get("draft_report"):
            final_report = data["draft_report"]

        if data.get("chart_specs"):
            chart_count = len(data["chart_specs"])
        if data.get("report_images"):
            image_count = len(data["report_images"])

    has_images = "data:image/png;base64" in final_report
    embedded_count = final_report.count("data:image/png;base64")

    print("\n=== FINAL REPORT ===\n")
    # Print report text but truncate base64 lines for readability
    for line in final_report.split("\n"):
        if "data:image/png;base64" in line:
            # Show just the markdown image alt text, not the blob
            print(line[:120] + "...<base64 image data>...")
        else:
            print(line)
    print("\n=== END REPORT ===")
    print(f"\n📊 Charts requested: {chart_count}")
    print(f"🖼️  Images embedded: {embedded_count}")
    if final_report:
        save_report(final_report, query)

# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run or test the lg_workflow_agent pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Full pipeline
  python -m src.lg_workflow_agent.run_sample
  python -m src.lg_workflow_agent.run_sample --stream "AI safety in 2026"

  # Test individual nodes (needs GOOGLE_API_KEY for LLM nodes)
  python -m src.lg_workflow_agent.run_sample --test-nodes
  python -m src.lg_workflow_agent.run_sample --test-nodes classifier writer

  # Test paper formatter (no API key needed)
  python -m src.lg_workflow_agent.run_sample --test-paper

  # Test chart renderer (no API key needed)
  python -m src.lg_workflow_agent.run_sample --test-charts

  # Run every test suite
  python -m src.lg_workflow_agent.run_sample --test-all
""",
    )
    parser.add_argument("query", nargs="*", help="Optional query (defaults to a comparative sample).")
    parser.add_argument("--stream", action="store_true", help="Use astream() and print step-by-step events.")
    parser.add_argument(
        "--test-nodes",
        nargs="*",
        default=None,
        metavar="NODE",
        help=(
            "Test individual workflow nodes. Pass node names to test specific ones, "
            "or omit to test all. Available: " + ", ".join(NODE_TESTS.keys())
        ),
    )
    parser.add_argument("--test-paper", action="store_true", help="Test the research paper formatter (validate, clean, compile).")
    parser.add_argument("--test-charts", action="store_true", help="Test the chart/visualisation renderer.")
    parser.add_argument("--test-all", action="store_true", help="Run all test suites (nodes, paper, charts).")
    args = parser.parse_args()

    # Determine which mode to run
    is_test = args.test_all or args.test_paper or args.test_charts or args.test_nodes is not None

    if is_test:
        suites_run = 0
        if args.test_all or args.test_nodes is not None:
            selected = args.test_nodes if args.test_nodes else None
            if args.test_all:
                selected = None  # run all
            if not os.environ.get("GOOGLE_API_KEY"):
                print("WARNING: GOOGLE_API_KEY is not set. LLM-based node tests will fail.\n", file=sys.stderr)
            run_node_tests(selected)
            suites_run += 1

        if args.test_all or args.test_charts:
            run_chart_tests()
            suites_run += 1

        if args.test_all or args.test_paper:
            run_paper_tests()
            suites_run += 1

        print(f"\n{'=' * 60}")
        print(f"   Done — {suites_run} test suite(s) executed")
        print(f"{'=' * 60}")
        return

    # Full pipeline run
    query = " ".join(args.query).strip() or DEFAULT_QUERY

    if not os.environ.get("GOOGLE_API_KEY"):
        print("WARNING: GOOGLE_API_KEY is not set. Gemini calls will fail.\n", file=sys.stderr)

    if args.stream:
        asyncio.run(run_stream(query))
    else:
        run_sync(query)


if __name__ == "__main__":
    main()