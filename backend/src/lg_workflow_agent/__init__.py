"""LangGraph-based workflow agent for automated research-oriented content generation.

Pipeline:
    Query Classifier -> Task Generator -> Specialized Sub-Agents (parallel)
    -> Data Aggregator -> Final Writer -> Validator (link-check / rewrite)
    -> Cleanup
"""

from .agent import WorkflowAgent
from .graph import WorkflowGraphBuilder
from .state import WorkflowState

__all__ = ["WorkflowAgent", "WorkflowGraphBuilder", "WorkflowState"]
