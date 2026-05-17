"""Assign Workers node — conditional fan-out to role sub-agent nodes."""

from __future__ import annotations

from langgraph.types import Send

from ..state import WorkflowState


def create_assign_workers():
    """Conditional fan-out: dispatch each payload to the matching role node."""

    role_to_node = {
        "data_collection": "data_collection_agent",
        "statistics": "statistics_agent",
        "citation": "citation_agent",
        "web_research": "web_research_agent",
        "latest_news_collection": "latest_news_collection_agent",
    }

    def assign(state: WorkflowState):
        sends = []
        for payload in state.get("worker_payloads", []):
            target = role_to_node.get(payload.get("role"))
            if target:
                sends.append(Send(target, payload))
        return sends

    return assign
