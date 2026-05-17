"""Task Generator node — decompose the query into role-tagged sub-tasks."""

from __future__ import annotations

import time
import logging
from typing import Any

from ..prompts import TASK_GENERATOR_PROMPT
from ..state import WorkflowState
from ..helpers import safe_json_load, persist
from ._constants import ROLES_BY_TYPE

logger = logging.getLogger(__name__)


def create_node_task_generator(llm, db):
    """Decompose the query into role-tagged sub-tasks."""

    def node_task_generator(state: WorkflowState):
        t0 = time.time()
        qtype = state.get("query_type", "summary")
        roles = ROLES_BY_TYPE[qtype]
        prompt = TASK_GENERATOR_PROMPT.format(
            query=state["query"],
            query_type=qtype,
            roles="\n".join(f"- {r}" for r in roles),
        )
        response = llm.invoke(prompt)
        parsed = safe_json_load(getattr(response, "content", "") or "")

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

        persist(db, state.get("task_id", ""), "task_generation",
                {"subtasks": subtasks})

        logger.info(f"[task_generator] {len(subtasks)} subtasks for {len(roles)} roles | {time.time() - t0:.1f}s")
        return {"subtasks": subtasks, "worker_payloads": payloads}

    return node_task_generator
