"""LangGraph node factories for the lg_workflow_agent workflow."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Send

from .prompts import (
    AGGREGATOR_PROMPT,
    CITATION_PROMPT,
    CLASSIFIER_PROMPT,
    CONTENT_DRAFTING_PROMPT,
    DATA_COLLECTION_PROMPT,
    REWRITE_NOTE_TEMPLATE,
    STATISTICS_PROMPT,
    TASK_GENERATOR_PROMPT,
    WEB_RESEARCH_PROMPT,
    WRITER_PROMPT,
)
from .state import WorkflowState
from .tools import extract_urls, fetch_trends, think_tool, validate_urls

# Map of role -> sub-agent system prompt.
ROLE_PROMPTS: dict[str, str] = {
    # deep_research roles
    "data_collection": DATA_COLLECTION_PROMPT,
    "statistics": STATISTICS_PROMPT,
    "citation": CITATION_PROMPT,
    # non-deep roles
    "web_research": WEB_RESEARCH_PROMPT,
    "content_drafting": CONTENT_DRAFTING_PROMPT,
}

# Roles available per query type.
ROLES_BY_TYPE: dict[str, list[str]] = {
    "deep_research": ["data_collection", "statistics", "citation"],
    "blog": ["web_research", "content_drafting"],
    "comparative": ["web_research", "content_drafting"],
    "summary": ["web_research", "content_drafting"],
}

MAX_REWRITES = 2


# --------------------------- helpers ---------------------------------------


def _safe_json_load(text: str) -> dict:
    """Load JSON from an LLM response, tolerating ```json fences."""
    if not text:
        return {}
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        # Try to extract first JSON object
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
        return {}


def _persist(db, task_id: str, stage: str, payload: Any) -> None:
    """Best-effort persistence of an intermediate stage to Qdrant."""
    if db is None or not task_id:
        return
    try:
        snippet = payload if isinstance(payload, str) else json.dumps(payload, default=str)[:8000]
        db.update_intermediate_report(task_id, f"[{stage}]\n{snippet}")
    except Exception:
        # Persistence is best-effort; never break the workflow.
        pass


# --------------------------- node factories --------------------------------


def create_node_classifier(llm, db):
    """Classify the user query into a research mode."""

    def node_classifier(state: WorkflowState):
        prompt = CLASSIFIER_PROMPT.format(query=state["query"])
        response = llm.invoke(prompt)
        parsed = _safe_json_load(getattr(response, "content", "") or "")

        qtype = parsed.get("query_type", "summary")
        if qtype not in ROLES_BY_TYPE:
            qtype = "summary"

        out = {
            "query_type": qtype,
            "classification_rationale": parsed.get("rationale", ""),
        }
        _persist(db, state.get("task_id", ""), "classify", out)
        return out

    return node_classifier


def create_node_task_generator(llm, db):
    """Decompose the query into role-tagged sub-tasks."""

    def node_task_generator(state: WorkflowState):
        qtype = state.get("query_type", "summary")
        roles = ROLES_BY_TYPE[qtype]
        prompt = TASK_GENERATOR_PROMPT.format(
            query=state["query"],
            query_type=qtype,
            roles="\n".join(f"- {r}" for r in roles),
        )
        response = llm.invoke(prompt)
        parsed = _safe_json_load(getattr(response, "content", "") or "")

        raw = parsed.get("subtasks", []) if isinstance(parsed, dict) else []
        subtasks: list[dict[str, Any]] = []
        for i, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            if role not in roles:
                role = roles[0]
            subtasks.append(
                {
                    "id": item.get("id", f"s{i}"),
                    "role": role,
                    "task": item.get("task", state["query"]),
                    "status": "pending",
                }
            )

        # Fallback: ensure at least one task per available role.
        if not subtasks:
            subtasks = [
                {"id": f"s{i}", "role": role, "task": state["query"], "status": "pending"}
                for i, role in enumerate(roles, start=1)
            ]

        # Build worker payloads for fan-out.
        payloads = [
            {
                "task_id": state.get("task_id", ""),
                "query": state["query"],
                "subtask_id": st["id"],
                "role": st["role"],
                "task": st["task"],
            }
            for st in subtasks
        ]

        _persist(db, state.get("task_id", ""), "task_generation",
                 {"subtasks": subtasks})

        return {"subtasks": subtasks, "worker_payloads": payloads}

    return node_task_generator


def create_assign_workers():
    """Conditional fan-out: dispatch each payload to the matching role node."""

    role_to_node = {
        "data_collection": "data_collection_agent",
        "statistics": "statistics_agent",
        "citation": "citation_agent",
        "web_research": "web_research_agent",
        "content_drafting": "content_drafting_agent",
    }

    def assign(state: WorkflowState):
        sends = []
        for payload in state.get("worker_payloads", []):
            target = role_to_node.get(payload.get("role"))
            if target:
                sends.append(Send(target, payload))
        return sends

    return assign


def _make_subagent_runner(llm, role: str, system_prompt: str, tools: list):
    """Build a worker function for a given role."""

    def runner(payload: dict[str, Any]):
        agent = create_agent(
            name=f"{role}_agent",
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
        )
        user_msg = (
            f"Query: {payload.get('query', '')}\n"
            f"Sub-task: {payload.get('task', '')}"
        )
        try:
            response = agent.invoke({"messages": [{"role": "user", "content": user_msg}]})
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

    return runner


def create_role_nodes(llm):
    """Return one node-callable per specialized sub-agent role."""
    tools = [fetch_trends, think_tool]
    return {
        "data_collection_agent": _make_subagent_runner(llm, "data_collection", DATA_COLLECTION_PROMPT, tools),
        "statistics_agent": _make_subagent_runner(llm, "statistics", STATISTICS_PROMPT, tools),
        "citation_agent": _make_subagent_runner(llm, "citation", CITATION_PROMPT, tools),
        "web_research_agent": _make_subagent_runner(llm, "web_research", WEB_RESEARCH_PROMPT, tools),
        "content_drafting_agent": _make_subagent_runner(llm, "content_drafting", CONTENT_DRAFTING_PROMPT, tools),
    }


def create_node_aggregator(llm, db):
    """Consolidate sub-agent outputs into a structured aggregated object."""

    def node_aggregator(state: WorkflowState):
        outputs = state.get("worker_outputs", [])
        rendered = "\n\n".join(
            f"### {o.get('role', '?')} :: {o.get('subtask_id', '?')}\n"
            f"Task: {o.get('task', '')}\n\n{o.get('output', '')}"
            for o in outputs
        ) or "(no outputs)"

        prompt = AGGREGATOR_PROMPT.format(
            query=state.get("query", ""),
            query_type=state.get("query_type", ""),
            outputs=rendered,
        )
        response = llm.invoke(prompt)
        parsed = _safe_json_load(getattr(response, "content", "") or "")

        # Sanity defaults.
        if not isinstance(parsed, dict) or "sections" not in parsed:
            parsed = {
                "metadata": {
                    "query": state.get("query", ""),
                    "query_type": state.get("query_type", ""),
                    "num_sources": 0,
                },
                "sections": [{"title": "Findings", "content": rendered}],
                "references": [],
            }

        _persist(db, state.get("task_id", ""), "aggregation", parsed)
        return {"aggregated": parsed}

    return node_aggregator


def create_node_writer(llm, db):
    """Produce the final markdown report from the aggregated structure."""

    def node_writer(state: WorkflowState):
        aggregated = state.get("aggregated", {})
        invalid_refs = state.get("invalid_references", [])
        rewrite_note = ""
        if invalid_refs:
            rewrite_note = REWRITE_NOTE_TEMPLATE.format(
                invalid_refs="\n".join(f"- {u}" for u in invalid_refs)
            )

        prompt = WRITER_PROMPT.format(
            aggregated=json.dumps(aggregated, indent=2, default=str),
            rewrite_note=rewrite_note,
        )
        response = llm.invoke(
            [SystemMessage(content="You write professional markdown reports."),
             HumanMessage(content=prompt)]
        )
        draft = response.content if isinstance(response.content, str) else str(response.content)

        _persist(db, state.get("task_id", ""), "draft", draft)
        # Reset invalid refs after applying them in a rewrite pass.
        return {"draft_report": draft, "invalid_references": []}

    return node_writer


def create_node_validator(db):
    """Verify all referenced links and trigger rewrites on broken refs."""

    def node_validator(state: WorkflowState):
        draft = state.get("draft_report", "")
        urls = extract_urls(draft)
        results = validate_urls(urls)
        broken = [u for u, ok in results.items() if not ok]

        iterations = state.get("rewrite_iterations", 0)

        if not broken:
            _persist(db, state.get("task_id", ""), "validation",
                     {"status": "VALID", "checked": len(urls)})
            return {
                "final_report": draft,
                "validation_feedback": "VALID",
                "invalid_references": [],
            }

        if iterations >= MAX_REWRITES:
            # Stop looping; strip broken URLs from the draft and accept it.
            cleaned = draft
            for u in broken:
                cleaned = cleaned.replace(u, "[broken link removed]")
            _persist(db, state.get("task_id", ""), "validation",
                     {"status": "FORCED_FINISH", "broken": broken})
            return {
                "final_report": cleaned,
                "validation_feedback": f"FORCED_FINISH after {iterations} rewrites",
                "invalid_references": [],
            }

        _persist(db, state.get("task_id", ""), "validation",
                 {"status": "BROKEN_REFS", "broken": broken})
        return {
            "validation_feedback": f"BROKEN_REFS: {len(broken)} link(s) failed",
            "invalid_references": broken,
            "rewrite_iterations": iterations + 1,
        }

    return node_validator


def create_validation_route():
    def route(state: WorkflowState):
        return "valid" if state.get("validation_feedback") == "VALID" or state.get("final_report") else "rewrite"
    return route


def create_node_cleanup(db):
    """Remove all intermediate task data; retain only the final report."""

    def node_cleanup(state: WorkflowState):
        if db is not None and state.get("task_id"):
            try:
                db.cleanup_task_data(state["task_id"])
            except Exception:
                pass
        if not state.get("final_report"):
            return {"final_report": state.get("draft_report", "No Report Generated")}
        return {}

    return node_cleanup
