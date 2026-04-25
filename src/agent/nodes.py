"""LangGraph node factories for the research workflow."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Send

from .model import AgentState
from .prompts import (
    PLANNER_PROMPT,
    REPORT_FORMAT_GUIDELINES,
    SUBAGENT_SYSTEM_PROMPT,
    VALIDATOR_PROMPT,
    WRITER_SYSTEM_PROMPT,
)
from .tools import fetch_trends
from langchain.agents import create_agent



RESEARCH_TYPES = {"blog", "comparative", "deep_research", "summary"}


def create_node_planner(llm, db):
    """Analyze intent, classify research mode, and create initial TODOs."""

    def node_planner(state: AgentState):
        prompt = PLANNER_PROMPT.format(date=date.today().isoformat(), query=state["query"]).strip()
        response = llm.invoke(prompt)

        try:
            parsed = json.loads(response.content)
        except Exception:
            parsed = {}

        todos = parsed.get("todos") if isinstance(parsed.get("todos"), list) else []
        if not todos:
            todos = [
                {"id": "t1", "task": f"Research and answer: {state['query']}", "status": "pending"}
            ]

        normalized = []
        for i, todo in enumerate(todos, start=1):
            task = todo.get("task", "Research task") if isinstance(todo, dict) else str(todo)
            normalized.append({"id": f"t{i}", "task": task, "status": "pending"})

        db.save_todos(state["task_id"], [t["task"] for t in normalized])

        research_type = parsed.get("research_type", "summary")
        if research_type not in RESEARCH_TYPES:
            research_type = "summary"

        return {
            "intent": parsed.get("intent", "research"),
            "goal": parsed.get("goal", state["query"]),
            "research_type": research_type,
            "todos": normalized,
        }

    return node_planner


def create_node_task_manager():
    """Reset ephemeral worker artifacts for each task round."""

    def node_task_manager(state: AgentState):
        return {"worker_payloads": [], "worker_findings": [], "current_todo": {}}

    return node_task_manager


def create_node_todo_selector():
    """Pick the next pending TODO."""

    def node_todo_selector(state: AgentState):
        for todo in state.get("todos", []):
            if todo.get("status") == "pending":
                return {"current_todo": todo}
        return {"current_todo": {}}

    return node_todo_selector


def create_node_delegation(_llm):
    """Create worker payloads so each pending TODO is processed in parallel."""

    def node_delegation(state: AgentState):
        pending_todos = [todo for todo in state.get("todos", []) if todo.get("status") == "pending"]
        if not pending_todos:
            return {"worker_payloads": []}

        query = state.get("query", "")
        payloads = []
        for i, todo in enumerate(pending_todos, start=1):
            task = todo.get("task", query)
            payloads.append(
                {
                    "worker_id": f"w{i}",
                    "task_id": state["task_id"],
                    "query": query,
                    "todo_id": todo.get("id", f"t{i}"),
                    "todo_task": task,
                }
            )
        return {"worker_payloads": payloads}

    return node_delegation


def create_assign_workers():
    """Return dynamic Send edges for worker fan-out."""

    def assign_workers(state: AgentState):
        return [Send("subagent", payload) for payload in state.get("worker_payloads", [])]

    return assign_workers


def create_node_subagent(llm):
    """Worker node that collects data for one delegated task using tools."""

    def node_subagent(state: dict[str, Any]):
        task = state.get("todo_task") or state.get("query", "")
        query = state.get("query", "")
        sub_agent = create_agent(
            name="research_subagent",
            model=llm,  # to be set at runtime
            tools=[fetch_trends],
            system_prompt=SUBAGENT_SYSTEM_PROMPT,)

        response = sub_agent.invoke(
            {"messages": [{"role": "user", "content": f"Task: {task} for  query: {query}"}]}
        )
        return {
            "worker_findings": [
                {   
                    "worker_id": state.get("worker_id", "w1"),
                    "todo_id": state.get("todo_id", "t1"),
                    "task": task,
                    "finding": response['messages'][-1].content[-1]['text'] or "No findings generated.",
                }
            ]
        }

    return node_subagent


def create_node_aggregator():
    """Merge worker findings for the selected TODO."""

    def node_aggregator(state: AgentState):
        findings = state.get("worker_findings", [])
        merged = "\n\n".join(f"- {f.get('finding', '')}" for f in findings if f.get("finding"))
        return {"aggregated_findings": merged or "No findings captured."}

    return node_aggregator


def create_node_context_synthesizer():
    """Create compact context from merged findings."""

    def node_context_synthesizer(state: AgentState):
        return {
            "synthesized_context": (
                f"Goal: {state.get('goal', '')}\n"
                f"Research type: {state.get('research_type', 'summary')}\n"
                f"Current findings:\n{state.get('aggregated_findings', '')}"
            )
        }

    return node_context_synthesizer


def create_node_todo_tracker(db):
    """Mark selected TODO as completed and store intermediate synthesis."""

    def node_todo_tracker(state: AgentState):
        completed_ids = {finding.get("todo_id") for finding in state.get("worker_findings", [])}
        updated = []
        for todo in state.get("todos", []):
            if todo.get("id") in completed_ids:
                updated.append({**todo, "status": "completed"})
            else:
                updated.append(todo)

        db.update_intermediate_report(state["task_id"], state.get("synthesized_context", ""))
        return {"todos": updated}

    return node_todo_tracker


def create_node_todo_checker():
    """No-op node used for loop routing."""

    def node_todo_checker(_: AgentState):
        return {}

    return node_todo_checker


def create_todo_route():
    def route(state: AgentState):
        has_pending = any(todo.get("status") == "pending" for todo in state.get("todos", []))
        return "has_pending" if has_pending else "all_done"

    return route


def create_node_writer(llm):
    """Generate draft report from synthesized context and workflow artifacts."""

    def node_writer(state: AgentState):
        feedback = state.get("validation_feedback", "")
        todos_summary = "\n".join(
            f"- [{t.get('status','pending')}] {t.get('task','')}" for t in state.get("todos", [])
        )

        prompt = (
            f"Query: {state['query']}\n"
            f"Research goal: {state.get('goal', '')}\n"
            f"Research type: {state.get('research_type', 'summary')}\n"
            f"Todos:\n{todos_summary}\n\n"
            f"Collected context:\n{state.get('synthesized_context', '')}\n\n"
            f"Formatting requirements:\n{REPORT_FORMAT_GUIDELINES}\n"
        )
        if feedback and feedback != "VALID":
            prompt += f"\nValidation feedback to fix:\n{feedback}\n"

        response = llm.invoke([SystemMessage(content=WRITER_SYSTEM_PROMPT), HumanMessage(content=prompt)])
        return {"draft_report": response.content}

    return node_writer


def create_node_validator(llm):
    """Validate draft report and return machine-readable status."""

    def node_validator(state: AgentState):
        draft = state.get("draft_report", "")
        iterations = state.get("validation_iterations", 0) + 1

        prompt = VALIDATOR_PROMPT.format(guidelines=REPORT_FORMAT_GUIDELINES, draft=draft)
        response = llm.invoke(prompt).content.strip()
        upper = response.upper()

        if "VALID" in upper:
            return {
                "final_report": draft,
                "validation_feedback": "VALID",
                "validation_iterations": iterations,
                "replan_reason": "",
            }

        replan_reason = ""
        if "RESEARCH GAP" in upper:
            replan_reason = response

        return {
            "validation_feedback": response,
            "validation_iterations": iterations,
            "replan_reason": replan_reason,
        }

    return node_validator


def create_validation_route():
    def route(state: AgentState):
        if state.get("validation_feedback") == "VALID":
            return "valid"
        if state.get("validation_iterations", 0) >= 3:
            return "force_finish"
        if state.get("replan_reason"):
            return "research_gap"
        return "format_issue"

    return route


def create_node_cleanup(db):
    """Cleanup temporary task data in vector store."""

    def node_cleanup(state: AgentState):
        db.cleanup_task_data(state["task_id"])
        if not state.get("final_report"):
            return {"final_report": state.get("draft_report", "No Report Generated")}
        return {}

    return node_cleanup


class ResearcherNode:
    """Compatibility wrapper for external imports."""


class WriterNode:
    """Compatibility wrapper for external imports."""
