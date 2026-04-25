import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.models import QueryRequest, QueryResponse, TaskStatusResponse, HealthResponse, ReportListResponse
from src.pipeline import ResearchPipeline

app = FastAPI(title="AI Research System")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
async def create_query(request: QueryRequest):
    """Answer a query by checking cache first, then falling back to the agent.

    When the agent must run, a streaming background coroutine is scheduled so
    that callers polling ``/status`` receive incremental step-by-step updates
    as the agent works through tool calls and LLM responses.
    """
    result = pipeline.process_query(request.query)

    if result["status"] == "processing":
        # Ensure the task record carries a steps list from the start
        pipeline._tasks[result["task_id"]]["steps"] = []
        # Fire-and-forget: streams step updates into the task record
        asyncio.create_task(
            pipeline.run_task_streaming(result["task_id"], request.query)
        )

    return QueryResponse(**result)


@app.get("/status", response_model=TaskStatusResponse)
def get_status(task_id: str):
    """Check the status of a background research task."""
    task = pipeline.get_task_status(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(**task)


@app.get("/report")
def get_all_reports():
    """Fetch all stored reports from the Qdrant database."""
    reports = pipeline.get_all_reports()
    return ReportListResponse(reports=reports)

@app.post("/cleanup")
def cleanup_db():
    """Wipe the database collection and any pending in-memory tasks."""
    pipeline.cleanup()
    return {"status": "cleaned"}

@app.post("/cleanup_all")
def cleanup_all_db():
    """Wipe all database collections and any pending in-memory tasks."""
    pipeline.cleanup_all()
    return {"status": "all_collections_cleaned"}


# Server runs via root run.py
