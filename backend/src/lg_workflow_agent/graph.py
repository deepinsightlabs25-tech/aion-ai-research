"""LangGraph construction for the lg_workflow_agent workflow."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import (
    create_assign_workers,
    create_node_aggregator,
    create_node_classifier,
    create_node_cleanup,
    create_node_paper_writer,
    create_node_report_finalizer,
    create_node_task_generator,
    create_node_validator,
    create_node_writer,
    create_role_nodes,
    create_validation_route,
)
from .state import WorkflowState


SUBAGENT_NODE_NAMES = [
    "data_collection_agent",
    "statistics_agent",
    "citation_agent",
    "web_research_agent",
    "latest_news_collection_agent",
]


class WorkflowGraphBuilder:
    """Builds the research-content-generation LangGraph workflow."""

    def __init__(self, llm, db=None):
        self.llm = llm
        self.db = db
        self._graph = None

    def build(self):
        if self._graph is not None:
            return self._graph

        wf = StateGraph(WorkflowState)

        wf.add_node("classifier", create_node_classifier(self.llm, self.db))
        wf.add_node("task_generator", create_node_task_generator(self.llm, self.db))

        # Specialized sub-agent nodes.
        role_nodes = create_role_nodes(self.llm)
        for name in SUBAGENT_NODE_NAMES:
            wf.add_node(name, role_nodes[name])

        wf.add_node("aggregator", create_node_aggregator(self.llm, self.db))
        wf.add_node("writer", create_node_writer(self.llm, self.db))
        wf.add_node("validator", create_node_validator(self.llm, self.db))
        wf.add_node("report_finalizer", create_node_report_finalizer(self.llm, self.db))
        wf.add_node("paper_writer", create_node_paper_writer(self.llm, self.db))
        wf.add_node("cleanup", create_node_cleanup(self.db))

        # Linear front: START -> classify -> task_gen -> fan-out
        wf.add_edge(START, "classifier")
        wf.add_edge("classifier", "task_generator")

        # Dynamic fan-out via Send to whichever role nodes are needed.
        wf.add_conditional_edges(
            "task_generator",
            create_assign_workers(),
            SUBAGENT_NODE_NAMES,
        )

        # All sub-agents fan in to aggregator.
        for name in SUBAGENT_NODE_NAMES:
            wf.add_edge(name, "aggregator")

        wf.add_edge("aggregator", "writer")
        wf.add_edge("writer", "validator")

        # Valid -> generate charts/images -> cleanup.  Invalid -> rewrite.
        wf.add_conditional_edges(
            "validator",
            create_validation_route(),
            {"valid": "report_finalizer", "rewrite": "writer"},
        )

        # After report_finalizer, generate paper (runs for all types but only
        # produces output for deep_research; the node itself short-circuits).
        wf.add_edge("report_finalizer", "paper_writer")
        wf.add_edge("paper_writer", "cleanup")
        wf.add_edge("cleanup", END)

        self._graph = wf.compile()
        return self._graph

    def invoke(self, initial_state: dict) -> dict:
        if self._graph is None:
            self.build()
        return self._graph.invoke(initial_state)

    async def astream(self, initial_state: dict):
        if self._graph is None:
            self.build()
        async for event in self._graph.astream(initial_state):
            yield event