"""LangGraph workflow construction and routing for the research agent."""

from langgraph.graph import END, START, StateGraph

from .model import AgentState
from .nodes import (
    create_assign_workers,
    create_node_aggregator,
    create_node_cleanup,
    create_node_context_synthesizer,
    create_node_delegation,
    create_node_planner,
    create_node_subagent,
    create_node_task_manager,
    create_node_todo_tracker,
    create_node_validator,
    create_node_writer,
    create_validation_route,
)


class GraphBuilder:
    """Builds and manages the LangGraph workflow."""

    def __init__(self, llm, llm_with_tools, db):
        self.llm = llm
        self.llm_with_tools = llm_with_tools
        self.db = db
        self._graph = None

    def build(self):
        if self._graph is not None:
            return self._graph

        workflow = StateGraph(AgentState)

        workflow.add_node("planner", create_node_planner(self.llm, self.db))
        workflow.add_node("task_manager", create_node_task_manager())
        workflow.add_node("delegation", create_node_delegation(self.llm))
        workflow.add_node("subagent", create_node_subagent(self.llm))
        workflow.add_node("aggregator", create_node_aggregator())
        workflow.add_node("context_synthesizer", create_node_context_synthesizer())
        workflow.add_node("todo_tracker", create_node_todo_tracker(self.db))
        workflow.add_node("writer", create_node_writer(self.llm))
        workflow.add_node("validator", create_node_validator(self.llm))
        workflow.add_node("cleanup", create_node_cleanup(self.db))

        workflow.add_edge(START, "planner")
        workflow.add_edge("planner", "task_manager")
        workflow.add_edge("task_manager", "delegation")

        # Dynamic fan-out using latest Send pattern
        workflow.add_conditional_edges("delegation", create_assign_workers(), ["subagent"])
        workflow.add_edge("subagent", "aggregator")
        workflow.add_edge("aggregator", "context_synthesizer")
        workflow.add_edge("context_synthesizer", "todo_tracker")
        workflow.add_edge("todo_tracker", "writer")

        workflow.add_edge("writer", "validator")
        workflow.add_conditional_edges(
            "validator",
            create_validation_route(),
            {
                "valid": "cleanup",
                "force_finish": "cleanup",
                "research_gap": "task_manager",
                "format_issue": "writer",
            },
        )

        workflow.add_edge("cleanup", END)

        self._graph = workflow.compile()
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
