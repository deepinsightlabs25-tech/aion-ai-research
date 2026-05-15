from pydantic import BaseModel
from typing import Optional, Dict, Any

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    status: str
    task_id: Optional[str] = None
    report: Optional[str] = None
    research_paper: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

class TaskStatusResponse(BaseModel):
    status: str
    report: Optional[str] = None
    error: Optional[str] = None
    steps: Optional[list] = None  # list of {"step": str, "content": str} dicts
    research_paper: Optional[Dict[str, Any]] = None  # LaTeX paper + metadata for deep_research

class ReportResponse(BaseModel):
    report: str

class HealthResponse(BaseModel):
    status: str

class ReportListResponse(BaseModel):
    reports: list  # List of {"id": str, "query": str, "report": str}


class AuthUserResponse(BaseModel):
    sub: str
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
