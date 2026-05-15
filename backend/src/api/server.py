import asyncio
import base64
import io
import logging
import os
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from src.api.auth import get_current_user
from src.api.models import (
    AuthUserResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ReportListResponse,
    TaskStatusResponse,
)
from src.pipeline import ResearchPipeline
from src.db.postgres import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

DEFAULT_CORS_ORIGINS = [
    "https://ai-report-gen.onrender.com",
    "http://localhost:5173",
    "http://localhost:5175",
    "https://deepinsightlabs25-tech.github.io",
    "https://aion-ai-research.onrender.com"
]


def _get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "").strip()
    if not configured:
        return DEFAULT_CORS_ORIGINS
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app = FastAPI(title="AI Research System")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single pipeline instance — owns the DB, agent, and task tracker
pipeline = ResearchPipeline()


@app.on_event("startup")
def startup_event():
    """Ensure the vector DB collection exists on server boot."""
    pipeline.initialize()
    db.create_tables()


@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/auth/me", response_model=AuthUserResponse)
def auth_me(user: dict = Depends(get_current_user)):
    """Validate the bearer token and return the current user profile."""
    return user


@app.post("/query", response_model=QueryResponse)
async def create_query(request: QueryRequest, user: dict = Depends(get_current_user)):
    """Answer a query by checking cache first, then falling back to the agent.

    When the agent must run, a streaming background coroutine is scheduled so
    that callers polling ``/status`` receive incremental step-by-step updates
    as the agent works through tool calls and LLM responses.
    """
    result = pipeline.process_query(request.query)

    if result["status"] == "processing":
        db.record_research_task(
            result["task_id"],
            user["sub"],
            request.query,
            email=user.get("email"),
            name=user.get("name"),
        )
        # Ensure the task record carries a steps list from the start
        pipeline._tasks[result["task_id"]]["steps"] = []
        # Fire-and-forget: streams step updates into the task record
        asyncio.create_task(
            pipeline.run_task_streaming(result["task_id"], request.query)
        )

    return QueryResponse(**result)


@app.get("/status", response_model=TaskStatusResponse)
def get_status(task_id: str, user: dict = Depends(get_current_user)):
    """Check the status of a background research task."""
    task = pipeline.get_task_status(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(**task)


@app.get("/paper/{task_id}")
def get_paper(task_id: str, user: dict = Depends(get_current_user)):
    """Retrieve the generated research paper for a completed task.

    Returns the compiled PDF as a downloadable file. If PDF compilation
    failed, returns the LaTeX source and metadata as JSON instead.
    """
    task = pipeline.get_task_status(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    paper = task.get("research_paper")
    if not paper:
        raise HTTPException(
            status_code=404,
            detail="No research paper available for this task (only generated for deep_research queries)",
        )

    pdf_base64 = paper.get("pdf_base64")
    if pdf_base64:
        pdf_bytes = base64.b64decode(pdf_base64)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=research_paper_{task_id[:8]}.pdf"
            },
        )

    return {
        "status": "pdf_not_available",
        "metadata": paper.get("metadata", {}),
        "latex": paper.get("latex", ""),
    }


@app.get("/report")
def get_all_reports(user: dict = Depends(get_current_user)):
    """Fetch all stored reports from the Qdrant database."""
    reports = pipeline.get_all_reports()
    return ReportListResponse(reports=reports)

@app.post("/cleanup")
def cleanup_db(user: dict = Depends(get_current_user)):
    """Wipe the database collection and any pending in-memory tasks."""
    pipeline.cleanup()
    return {"status": "cleaned"}

@app.post("/cleanup_all")
def cleanup_all_db(user: dict = Depends(get_current_user)):
    """Wipe all database collections and any pending in-memory tasks."""
    pipeline.cleanup_all()
    return {"status": "all_collections_cleaned"}


# Server runs via root run.py
