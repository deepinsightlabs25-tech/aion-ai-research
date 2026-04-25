import os
import uuid
from typing import AsyncGenerator, Any, Dict
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from .tools import fetch_trends, think_tool
from .graph import GraphBuilder
from src.db.database import VectorDBContext


class ResearchAgent:
    """
    Main agent class orchestrating the research workflow.
    
    Delegates graph building to GraphBuilder and node operations
    to individual node factories in nodes.py.
    """
    
    def __init__(self):
        self.db = VectorDBContext()
        self._graph_builder = None
        self._graph = None

    @property
    def is_ready(self) -> bool:
        """Check if agent has been built and is ready to invoke."""
        return self._graph is not None

    def build(self) -> None:
        """
        Initialize the LLM and build the workflow graph.
        
        Safe to call multiple times; subsequent calls are no-ops
        if the graph is already built.
        """
        if self._graph is not None:
            return

        # Initialize LLM
        model_name = os.environ.get("DEEP_AGENT_MODEL", "gemini-2.5-flash")
        if model_name.startswith("google_genai:"):
            model_name = model_name.split(":")[1]

        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.0)
        tools = [fetch_trends, think_tool]
        llm_with_tools = llm.bind_tools(tools)

        # Build the graph using GraphBuilder
        self._graph_builder = GraphBuilder(llm, llm_with_tools, self.db)
        self._graph = self._graph_builder.build()

    def invoke(self, query: str) -> str:
        """
        Execute the research workflow synchronously.
        
        Args:
            query: The research query string
            
        Returns:
            The final report as a string
            
        Raises:
            RuntimeError: If agent hasn't been built yet
        """
        if self._graph is None:
            raise RuntimeError("Agent not built. Call build() first.")
            
        task_id = str(uuid.uuid4())
        initial_state = {
            "query": query,
            "task_id": task_id,
            "messages": [HumanMessage(content=query)],
            "validation_iterations": 0
        }
        
        result = self._graph_builder.invoke(initial_state)
        return result.get("final_report", "No Report Generated")

    async def astream(self, query: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the research workflow asynchronously with streaming.
        
        Args:
            query: The research query string
            
        Yields:
            Event dictionaries containing step info, content, and full state
            
        Raises:
            RuntimeError: If agent hasn't been built yet
        """
        if self._graph is None:
            raise RuntimeError("Agent not built. Call build() first.")
            
        task_id = str(uuid.uuid4())
        initial_state = {
            "query": query,
            "task_id": task_id,
            "messages": [HumanMessage(content=query)],
            "validation_iterations": 0
        }

        async for event in self._graph_builder.astream(initial_state):
            for node, state in event.items():
                # SAFETY CHECK: Skip if state is None or not a dictionary 
                if state is None or not isinstance(state, dict):
                    continue
                    
                content = state.get("draft_report") or state.get("final_report") or ""
                yield {
                    "step": f"step: {node}",
                    "content": content,
                    "data": state
                }