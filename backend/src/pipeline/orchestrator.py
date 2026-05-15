import uuid
import logging
from typing import Dict, List, Any, Optional

from src.db.database import VectorDBContext
from src.lg_workflow_agent import WorkflowAgent

logger = logging.getLogger(__name__)


class ResearchPipeline:
    """Orchestrates the full research query lifecycle.

    Pipeline flow:
        1. Check vector DB cache for a semantically similar past query.
        2. If cache miss, create a tracked background task.
        3. Execute the research agent to generate a report.
        4. Persist the result back into the vector DB.

    This class is the single entry point for all business logic;
    the API layer delegates exclusively to it.
    """

    def __init__(
        self,
        db: Optional[VectorDBContext] = None,
        agent: Optional[WorkflowAgent] = None,
    ):
        self.db = db or VectorDBContext()
        self.agent = agent or WorkflowAgent(db=self.db)
        self._tasks: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Prepare all subsystems — called once at service startup.

        Initialises the vector DB collection and builds the research agent.
        """
        self.db.init_db()
        self.agent.build()

    # ------------------------------------------------------------------
    # Query pipeline
    # ------------------------------------------------------------------

    def process_query(self, query: str) -> Dict[str, Any]:
        """Check cache and return a cached report or a new task_id.

        Returns:
            dict with keys ``status``, and optionally ``report``/``research_paper``
            or ``task_id``.
        """
        # Step 1 — cache lookup
        cached = self.db.search_query(query)
        if cached:
            result: Dict[str, Any] = {"status": "found", "report": cached["report"]}
            if cached.get("paper_latex"):
                result["research_paper"] = {
                    "latex": cached["paper_latex"],
                    "metadata": {},
                }
            return result

        # Step 2 — cache miss → create a pending task
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {"status": "pending", "report": None, "error": None}
        return {"status": "processing", "task_id": task_id}

    def _init_task(
        self, task_id: str, status: str = "pending"
    ) -> Dict[str, Any]:
        """Create a fresh task record and register it."""
        record: Dict[str, Any] = {
            "status": status,
            "report": None,
            "error": None,
            "steps": [],
        }
        self._tasks[task_id] = record
        return record

    def run_task(self, task_id: str, query: str) -> None:
        """Execute the research agent, persist the report, and update task state.

        Designed to be called as a background task by the API layer.
        """
        try:
            self._tasks[task_id]["status"] = "processing"

            report = self.agent.invoke(query)
            
            if report and report != " No Report Generated":
                self.db.save_report(query, report)
                logger.info(f"Task {task_id}: Report successfully saved to Qdrant DB")
                self._tasks[task_id]["status"] = "completed"
                self._tasks[task_id]["report"] = report
            else:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = "No valid report generated"
                logger.error(f"Task {task_id}: Failed to generate valid report")
                
        except Exception as exc:
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = str(exc)
            logger.exception("Task %s failed", task_id)

    async def run_task_streaming(self, task_id: str, query: str) -> None:
        """Execute the agent asynchronously, streaming per-step progress updates.

        After each agent step (LLM call, tool invocation, …) the task record's
        ``steps`` list is updated **in place** so callers polling ``/status``
        will see incremental progress without waiting for the full run.

        Designed to be scheduled with ``asyncio.create_task()`` or as a
        FastAPI background task on an ``async def`` route.
        """
        import time
        pipeline_start = time.time()

        task = self._tasks.get(task_id)
        if task is None:
            logger.error("run_task_streaming called for unknown task_id %s", task_id)
            return

        task["status"] = "processing"
        task["steps"] = []
        last_content = ""
        research_paper_data: Optional[Dict[str, Any]] = None

        try:
            async for update in self.agent.astream(query):
                step_record = {
                    "step": update["step"],
                    "content": update["content"],
                    "metadata": update.get("data", {}),
                }
                task["steps"].append(step_record)
                logger.debug(
                    "Task %s — step %s: %s",
                    task_id,
                    update["step"],
                    update["content"][:120],
                )
                # Track last non-empty content so we can surface the final report
                if update["content"]:
                    last_content = update["content"]

                # Capture research paper output from the paper_writer node
                step_data = update.get("data", {})
                if step_data.get("research_paper_latex"):
                    research_paper_data = {
                        "latex": step_data["research_paper_latex"],
                        "metadata": step_data.get("research_paper_metadata", {}),
                        "pdf_base64": step_data.get("research_paper_pdf_base64"),
                    }

            # Ensure we have captured the final report content
            if last_content:
                paper_latex = research_paper_data.get("latex") if research_paper_data else None
                self.db.save_report(query, last_content, paper_latex=paper_latex)
                elapsed = time.time() - pipeline_start
                logger.info(f"Task {task_id}: Report saved ({len(last_content)} chars) | total pipeline time: {elapsed:.1f}s")
                task["status"] = "completed"
                task["report"] = last_content
                if research_paper_data:
                    task["research_paper"] = research_paper_data
                    logger.info(f"Task {task_id}: Research paper saved to Qdrant ({len(paper_latex or '')} chars)")
            else:
                # If no content from streaming, try to get the final report via invoke
                final_report = self.agent.invoke(query)
                if final_report and final_report != " No Report Generated":
                    self.db.save_report(query, final_report)
                    elapsed = time.time() - pipeline_start
                    logger.info(f"Task {task_id}: Final report saved (fallback invoke, {len(final_report)} chars) | total: {elapsed:.1f}s")
                    task["status"] = "completed"
                    task["report"] = final_report
                else:
                    task["status"] = "failed"
                    task["error"] = "No report content generated"
                    
        except Exception as exc:
            elapsed = time.time() - pipeline_start
            task["status"] = "failed"
            task["error"] = str(exc)
            logger.exception("Task %s failed after %.1fs", task_id, elapsed)

    # ------------------------------------------------------------------
    # Task status
    # ------------------------------------------------------------------

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Return the current status dict for a task, or ``None`` if unknown."""
        return self._tasks.get(task_id)

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_all_reports(self) -> List[Dict[str, Any]]:
        """Retrieve every stored report from the vector DB."""
        return self.db.get_reports()

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Wipe the vector DB collection and clear all in-memory tasks."""
        self.db.cleanup()
        self._tasks.clear()

    def cleanup_all(self) -> None:
        """Wipe all vector DB collections and clear in-memory tasks."""
        self.db.cleanup_all()
        self._tasks.clear()

    # ----------------------------------------------------------------------
    # Full cleanup (DB + in-memory state)
    # ----------------------------------------------------------------------
    def full_cleanup(self) -> None:
        """Same as :meth:`cleanup_all` — clears all collections and task state."""
        self.cleanup_all()
