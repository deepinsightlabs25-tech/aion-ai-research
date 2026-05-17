"""Workflow state definition for the lg_workflow_agent LangGraph pipeline."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages

QueryType = Literal["blog", "comparative", "deep_research", "summary", "ambiguous"]


class WorkflowState(TypedDict, total=False):
    # Inputs
    query: str
    task_id: str
    messages: Annotated[list, add_messages]

    # Classification
    query_type: QueryType
    classification_rationale: str
    ambiguous_reason: str
    is_ambiguous: bool

    # Task decomposition
    subtasks: list[dict[str, Any]]              # [{id, role, task, status}]
    worker_payloads: list[dict[str, Any]]       # fan-out payloads

    # Sub-agent outputs (fan-in via reducer)
    worker_outputs: Annotated[list[dict[str, Any]], add]

    # Aggregation
    aggregated: dict[str, Any]                  # {sections, references, metadata}

    # Report lifecycle
    draft_report: str
    final_report: str

    # Visual enrichment
    chart_specs: list[dict[str, Any]]               # chart specifications from LLM
    report_images: list[dict[str, str]]              # [{caption, data_uri}]

    # Validation / control
    validation_feedback: str
    invalid_references: list[str]
    rewrite_iterations: int

    # Research paper output (generated for deep_research queries)
    research_paper_latex: str
    research_paper_metadata: dict[str, Any]
    research_paper_pdf_base64: str | None
    research_paper_images: list[dict[str, str]]      # [{filename, data_uri, caption}]