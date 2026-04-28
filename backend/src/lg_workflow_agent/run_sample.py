"""Sample run script for the lg_workflow_agent.

Usage (from the backend/ directory with the venv activated):

    python -m src.lg_workflow_agent.run_sample
    python -m src.lg_workflow_agent.run_sample "your custom query here"
    python -m src.lg_workflow_agent.run_sample --stream "your custom query"

Requires environment variables:
    GOOGLE_API_KEY        (for Gemini)
    DEEP_AGENT_MODEL      (optional, defaults to gemini-2.5-flash)
    QDRANT_URL/API_KEY    (optional; falls back to in-memory Qdrant)
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import os
import sys
from pathlib import Path
import json

# Ensure backend/ is on sys.path when run as a script (not as -m).
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from src.lg_workflow_agent import WorkflowAgent  # noqa: E402


REPORTS_DIR = BACKEND_ROOT / "reports"


def save_report(report: str, query: str) -> Path:
    """Save *report* to a timestamped markdown file under reports/."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = query[:40].strip().replace(" ", "_").replace("/", "-")
    filename = f"report_{timestamp}_{slug}.md"
    path = REPORTS_DIR / filename
    path.write_text(f"# Research Report\n\n**Query:** {query}\n\n---\n\n{report}\n", encoding="utf-8")
    print(f"\n[Report saved -> {path}]")
    return path


DEFAULT_QUERY = (
    "Compare LangGraph vs CrewAI vs AutoGen for building multi-agent research "
    "assistants in 2026 — focus on orchestration model, streaming, and tool use."
)


def run_sync(query: str) -> None:
    print(f"\n=== Building WorkflowAgent ===")
    agent = WorkflowAgent()
    agent.build()
    print(f"Agent ready. Running query:\n  {query}\n")

    print("=== Invoking workflow (sync) ===")
    report = agent.invoke(query)

    print("\n=== FINAL REPORT ===\n")
    print(report)
    print("\n=== END REPORT ===")
    save_report(report, query)


async def run_stream(query: str) -> None:
    print(f"\n=== Building WorkflowAgent (streaming) ===")
    agent = WorkflowAgent()
    agent.build()
    print(f"Agent ready. Streaming query:\n  {query}\n")

    final_report = ""
    async for event in agent.astream(query):
        step = event.get("step", "?")
        data = event.get("data", {})

        # Compact per-step trace
        keys = sorted(k for k in data.keys() if k != "messages")
        print(f"~~~~~~~~~~~~~~~~~~~~~~ [{step}] keys={keys} \n | data : {json.dumps(data , indent=2)}\n \n ")
        # if data.get("query_type"):
        #     print(f"    query_type = {data['query_type']}")
        # if data.get("subtasks"):
        #     for st in data["subtasks"]:
        #         print(f"    subtask {st['id']} [{st['role']}] -> {st['task']}")
        # if data.get("validation_feedback"):
        #     print(f"    validation = {data['validation_feedback']}")
        if data.get("final_report"):
            final_report = data["final_report"]
        elif data.get("draft_report"):
            final_report = data["draft_report"]

    print("\n=== FINAL REPORT ===\n")
    print(final_report or "(no report produced)")
    print("\n=== END REPORT ===")
    if final_report:
        save_report(final_report, query)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lg_workflow_agent on a sample query.")
    parser.add_argument("query", nargs="*", help="Optional query (defaults to a comparative sample).")
    parser.add_argument("--stream", action="store_true", help="Use astream() and print step-by-step events.")
    args = parser.parse_args()

    query = " ".join(args.query).strip() or DEFAULT_QUERY

    if not os.environ.get("GOOGLE_API_KEY"):
        print("WARNING: GOOGLE_API_KEY is not set. Gemini calls will fail.\n", file=sys.stderr)

    if args.stream:
        asyncio.run(run_stream(query))
    else:
        run_sync(query)


if __name__ == "__main__":
    main()