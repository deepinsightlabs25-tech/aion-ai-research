from __future__ import annotations

"""State definition for the LangGraph research workflow."""

from operator import add
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # Core request context
    query: str
    task_id: str

    # Conversation + tool loop context
    messages: Annotated[list, add_messages]

    # Planning / execution
    intent: str
    goal: str
    research_type: Literal["blog", "comparative", "deep_research", "summary"]
    todos: list[dict[str, Any]]
    current_todo: dict[str, Any]

    # Parallel sub-agent style outputs (fan-out/fan-in)
    worker_payloads: list[dict[str, Any]]
    worker_findings: Annotated[list[dict[str, Any]], add]
    aggregated_findings: str
    synthesized_context: str

    # Report lifecycle
    draft_report: str
    final_report: str

    # Validation / control
    validation_feedback: str
    validation_iterations: int
    replan_reason: str
