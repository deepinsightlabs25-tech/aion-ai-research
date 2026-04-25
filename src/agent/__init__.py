"""
Research Agent Package

Provides the main ResearchAgent class and supporting modules for
building and running automated research workflows using LangGraph.

Module structure:
- core.py: Main ResearchAgent orchestrator
- graph.py: GraphBuilder for workflow construction
- nodes.py: Individual node implementations
- model.py: AgentState TypedDict definition
- tools.py: Tool definitions for the agent
- prompts.py: System prompts and templates
"""

from .core import ResearchAgent
from .model import AgentState
from .graph import GraphBuilder
from .nodes import (
    ResearcherNode,
    WriterNode,
    create_assign_workers,
    create_node_aggregator,
    create_node_context_synthesizer,
    create_node_delegation,
    create_node_planner,
    create_node_cleanup,
    create_node_subagent,
    create_node_task_manager,
    create_node_todo_checker,
    create_node_todo_selector,
    create_node_todo_tracker,
    create_node_validator,
    create_node_writer,
    create_todo_route,
    create_validation_route,
)

__all__ = [
    "ResearchAgent",
    "AgentState",
    "GraphBuilder",
    "ResearcherNode",
    "WriterNode",
    "create_assign_workers",
    "create_node_aggregator",
    "create_node_context_synthesizer",
    "create_node_delegation",
    "create_node_planner",
    "create_node_cleanup",
    "create_node_subagent",
    "create_node_task_manager",
    "create_node_todo_checker",
    "create_node_todo_selector",
    "create_node_todo_tracker",
    "create_node_validator",
    "create_node_writer",
    "create_todo_route",
    "create_validation_route",
]
