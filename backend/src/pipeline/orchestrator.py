import gc
import uuid
import logging
import time
from collections import OrderedDict
from typing import Dict, List, Any, Optional

from src.db.database import VectorDBContext
from src.lg_workflow_agent import WorkflowAgent

logger = logging.getLogger(__name__)

_MAX_TASKS = 5  # Maximum number of completed tasks to keep in memory
_TASK_TTL = 600  # Seconds to keep completed/failed tasks (10 minutes)

# Keys in step metadata that may hold large payloads (base64 PDFs/PNGs, full text)
_HEAVY_STEP_KEYS = (
    "research_paper_pdf_base64",
    "research_paper_latex",
    "research_paper_metadata",
    "charts",
    "final_report",
    "report",
    "sections",
    "aggregated",
    "sub_agent_outputs",
    "context",
)


def _release_memory() -> None:
    """Force release of process memory after a task finishes.

    Closes any open matplotlib figures (chart_generator may leave the
    pyplot state alive) and runs a full GC pass.
    """
    try:
        from src.lg_workflow_agent import chart_generator as _cg
        if _cg.plt is not None:
            _cg.plt.close("all")
    except Exception:
        pass
    gc.collect()


class _EvictingTaskStore:
    """Bounded task store that evicts old completed/failed tasks."""

    def __init__(self, max_tasks: int = _MAX_TASKS, ttl: int = _TASK_TTL):
        self._tasks: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_tasks = max_tasks
        self._ttl = ttl

    def __setitem__(self, key: str, value: Dict[str, Any]) -> None:
        value.setdefault("_created_at", time.time())
        self._tasks[key] = value
        self._evict()

    def __getitem__(self, key: str) -> Dict[str, Any]:
        return self._tasks[key]

    def __contains__(self, key: str) -> bool:
        return key in self._tasks

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(key)

    def _evict(self) -> None:
        now = time.time()
        # Remove expired completed/failed tasks
        expired = [
            k for k, v in self._tasks.items()
            if v.get("status") in ("completed", "failed")
            and now - v.get("_created_at", now) > self._ttl
        ]
        for k in expired:
            del self._tasks[k]
        # If still over limit, drop oldest completed/failed tasks
        while len(self._tasks) > self._max_tasks:
            for k, v in list(self._tasks.items()):
                if v.get("status") in ("completed", "failed"):
                    del self._tasks[k]
                    break
            else:
                # No completed task to evict — drop the oldest entry anyway
                # to enforce the hard cap and prevent unbounded growth.
                oldest = next(iter(self._tasks))
                del self._tasks[oldest]


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
        self._tasks = _EvictingTaskStore()

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
                paper_data: Dict[str, Any] = {
                    "latex": cached["paper_latex"],
                    "metadata": {},
                }
                # Re-compile PDF from cached LaTeX (fast, ~1s)
                try:
                    from src.lg_workflow_agent.paper_formatter import compile_latex_to_pdf, pdf_to_base64
                    pdf_bytes, _ = compile_latex_to_pdf(cached["paper_latex"])
                    if pdf_bytes:
                        paper_data["pdf_base64"] = pdf_to_base64(pdf_bytes)
                except Exception:
                    pass
                result["research_paper"] = paper_data
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

    def _finalize_task(self, task_id: str) -> None:
        """Strip heavy intermediate data from a finished task and free memory.

        After completion, the per-step metadata (which may include base64
        chart PNGs, PDF bytes, full LLM outputs, etc.) is no longer needed:
        the final report and research_paper are already top-level fields.
        Removing it before GC reclaims tens of MB per task.
        """
        task = self._tasks.get(task_id)
        if task is None:
            return
        steps = task.get("steps") or []
        for step in steps:
            meta = step.get("metadata")
            if not isinstance(meta, dict):
                continue
            for k in _HEAVY_STEP_KEYS:
                meta.pop(k, None)
            # Truncate any remaining large string values
            for k, v in list(meta.items()):
                if isinstance(v, str) and len(v) > 2048:
                    meta[k] = v[:512] + f"... [{len(v)} chars truncated]"
        _release_memory()

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
        finally:
            self._finalize_task(task_id)

    async def run_task_streaming(self, task_id: str, query: str) -> None:
        """Execute the agent asynchronously, streaming per-step progress updates.

        After each agent step (LLM call, tool invocation, …) the task record's
        ``steps`` list is updated **in place** so callers polling ``/status``
        will see incremental progress without waiting for the full run.

        Designed to be scheduled with ``asyncio.create_task()`` or as a
        FastAPI background task on an ``async def`` route.
        """
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
                step_data = update.get("data", {}) or {}

                # Capture research paper output from the paper_writer node
                # BEFORE we strip step_data so the top-level dict keeps the
                # full payload while task["steps"] stays light-weight.
                if step_data.get("research_paper_latex"):
                    research_paper_data = {
                        "latex": step_data["research_paper_latex"],
                        "metadata": step_data.get("research_paper_metadata", {}),
                        "pdf_base64": step_data.get("research_paper_pdf_base64"),
                    }

                # Build a lightweight metadata dict: drop heavy payloads
                # (base64 PDFs/PNGs, full report duplicates, etc.) so each
                # accumulated step record stays in the kilobytes range.
                light_meta: Dict[str, Any] = {}
                for k, v in step_data.items():
                    if k in _HEAVY_STEP_KEYS:
                        continue
                    if isinstance(v, str) and len(v) > 2048:
                        light_meta[k] = v[:512] + f"... [{len(v)} chars truncated]"
                    else:
                        light_meta[k] = v

                step_record = {
                    "step": update["step"],
                    "content": update["content"],
                    "metadata": light_meta,
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
        finally:
            self._finalize_task(task_id)

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
