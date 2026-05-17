"""Best-effort persistence of intermediate workflow stages."""

from __future__ import annotations

import json
from typing import Any


def persist(db, task_id: str, stage: str, payload: Any) -> None:
    """Best-effort persistence of an intermediate stage to Qdrant."""
    if db is None or not task_id:
        return
    try:
        snippet = payload if isinstance(payload, str) else json.dumps(payload, default=str)[:8000]
        db.update_intermediate_report(task_id, f"[{stage}]\n{snippet}")
    except Exception:
        # Persistence is best-effort; never break the workflow.
        pass
