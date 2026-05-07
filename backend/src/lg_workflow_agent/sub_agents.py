"""Pre-built sub-agents for the lg_workflow_agent workflow.

Sub-agents (LangChain ``create_agent`` instances) are constructed **once** at
build time via :func:`build_sub_agents` and reused across every workflow
invocation. The matching :class:`SubAgentRunner` is a lightweight callable
that only invokes the pre-built agent on each run — no per-call construction.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from langchain.agents import create_agent

from .prompts import (
    CITATION_PROMPT,
    DATA_COLLECTION_PROMPT,
    LATEST_NEWS_COLLECTION_PROMPT,
    STATISTICS_PROMPT,
    WEB_RESEARCH_PROMPT,
)
from .tools import (
    fetch_arxiv,
    fetch_github,
    fetch_google_news,
    fetch_hackernews,
    fetch_linkedin,
    fetch_podcasts,
    fetch_reddit,
    fetch_rss,
    fetch_youtube,
    think_tool,
)

__all__ = ["build_sub_agents", "build_role_runners"]

# Role-specific tool sets — each agent only gets tools relevant to its task
_ROLE_TOOLS: dict[str, list] = {
    "data_collection": [
        fetch_hackernews,
        fetch_github,
        fetch_reddit,
        fetch_rss,
        fetch_google_news,
        think_tool,
    ],
    "statistics": [
        fetch_github,
        fetch_hackernews,
        fetch_arxiv,
        fetch_youtube,
        think_tool,
    ],
    "citation": [
        fetch_arxiv,
        fetch_rss,
        fetch_google_news,
        fetch_github,
        think_tool,
    ],
    "web_research": [
        fetch_hackernews,
        fetch_youtube,
        fetch_github,
        fetch_linkedin,
        fetch_reddit,
        fetch_rss,
        fetch_google_news,
        think_tool,
    ],
    "latest_news_collection": [
        fetch_google_news,
        fetch_hackernews,
        fetch_reddit,
        fetch_rss,
        fetch_arxiv,
        fetch_podcasts,
        think_tool,
    ],
}

# Role -> (agent name suffix, system prompt)
_ROLE_SPECS: dict[str, tuple[str, str]] = {
    "data_collection": ("data_collection_agent", DATA_COLLECTION_PROMPT),
    "statistics": ("statistics_agent", STATISTICS_PROMPT),
    "citation": ("citation_agent", CITATION_PROMPT),
    "web_research": ("web_research_agent", WEB_RESEARCH_PROMPT),
    "latest_news_collection": ("latest_news_collection_agent", LATEST_NEWS_COLLECTION_PROMPT),
}


def build_sub_agents(llm, tools: list | None = None) -> dict[str, Any]:
    """Construct one ``create_agent`` instance per role.

    Called once during graph build. Returns a mapping of ``role -> agent``.
    Each role receives only the tools relevant to its task.
    """
    agents: dict[str, Any] = {}
    for role, (name, prompt) in _ROLE_SPECS.items():
        role_tools = tools if tools is not None else _ROLE_TOOLS[role]
        agents[role] = create_agent(
            name=name,
            model=llm,
            tools=role_tools,
            system_prompt=prompt,
        )
    return agents


def _make_runner(role: str, agent: Any) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Build a lightweight async runner that invokes a *pre-built* agent."""

    _logger = logging.getLogger(__name__)

    async def runner(payload: dict[str, Any]) -> dict[str, Any]:
        t0 = time.time()
        user_msg = (
            f"Query: {payload.get('query', '')}\n"
            f"Sub-task: {payload.get('task', '')}"
        )
        try:
            response = await agent.ainvoke({"messages": [{"role": "user", "content": user_msg}]})
            last = response["messages"][-1].content
            if isinstance(last, list):
                # Gemini-style multi-part content.
                text = next(
                    (p.get("text", "") for p in last if isinstance(p, dict) and p.get("text")),
                    "",
                )
            else:
                text = last or ""
        except Exception as exc:
            text = f"Sub-agent {role} failed: {exc}"

        _logger.info(f"[sub_agent:{role}] {len(text)} chars | {time.time() - t0:.1f}s")

        return {
            "worker_outputs": [
                {
                    "subtask_id": payload.get("subtask_id"),
                    "role": role,
                    "task": payload.get("task", ""),
                    "output": text or "No output produced.",
                }
            ]
        }

    runner.__name__ = f"{role}_runner"
    return runner


def build_role_runners(llm, tools: list | None = None) -> dict[str, Callable]:
    """Build sub-agents once and return ``node_name -> runner`` mapping.

    The returned dict is keyed by graph node name (e.g. ``data_collection_agent``)
    so it can be plugged straight into the LangGraph workflow.
    """
    agents = build_sub_agents(llm, tools=tools)
    return {
        _ROLE_SPECS[role][0]: _make_runner(role, agent)
        for role, agent in agents.items()
    }