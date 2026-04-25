from pydantic import BaseModel
from typing import Optional, Dict, Any

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    status: str
    task_id: Optional[str] = None
    report: Optional[str] = None
    message: Optional[str] = None

class TaskStatusResponse(BaseModel):
    status: str
    report: Optional[str] = None
    error: Optional[str] = None
    steps: Optional[list] = None  # list of {"step": str, "content": str} dicts

class ReportResponse(BaseModel):
    report: str

class HealthResponse(BaseModel):
    status: str

class ReportListResponse(BaseModel):
    reports: list  # List of {"id": str, "query": str, "report": str}
