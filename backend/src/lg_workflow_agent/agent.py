"""Top-level workflow agent runtime entry point."""

from __future__ import annotations

import os
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.db.database import VectorDBContext
from .graph import WorkflowGraphBuilder


class WorkflowAgent:
    """Public API for the lg_workflow_agent research/content workflow."""

    def __init__(self, db: Optional[VectorDBContext] = None):
        self.db = db if db is not None else VectorDBContext()
        self._builder: Optional[WorkflowGraphBuilder] = None
        self._graph = None

    @property
    def is_ready(self) -> bool:
        return self._graph is not None

    def build(self) -> None:
        if self._graph is not None:
            return
        model_name = os.environ.get("DEEP_AGENT_MODEL", "gemini-2.5-flash")
        if model_name.startswith("google_genai:"):
            model_name = model_name.split(":", 1)[1]

        # Performance optimization: Production-safe retries
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.0,
            max_retries=2,  # Retry on transient failures
        )
        self._builder = WorkflowGraphBuilder(llm=llm, db=self.db)
        self._graph = self._builder.build()

    def _initial_state(self, query: str) -> Dict[str, Any]:
        return {
            "query": query,
            "task_id": str(uuid.uuid4()),
            "messages": [HumanMessage(content=query)],
            "rewrite_iterations": 0,
            "invalid_references": [],
        }

    def invoke(self, query: str) -> str:
        if self._graph is None:
            raise RuntimeError("Agent not built. Call build() first.")
        result = self._builder.invoke(self._initial_state(query))
        return result.get("final_report") or result.get("draft_report") or "No Report Generated"

    async def astream(self, query: str) -> AsyncGenerator[Dict[str, Any], None]:
        if self._graph is None:
            raise RuntimeError("Agent not built. Call build() first.")
        async for event in self._builder.astream(self._initial_state(query)):
            for node, state in event.items():
                if state is None or not isinstance(state, dict):
                    continue
                content = state.get("final_report") or state.get("draft_report") or ""
                yield {"step": f"step: {node}", "content": content, "data": state}