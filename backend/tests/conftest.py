"""
conftest.py — shared pytest fixtures for the entire test suite.

Provides:
  - in-memory VectorDBContext (no Qdrant cloud needed)
  - a pre-built mock WorkflowAgent
  - a ResearchPipeline wired to both stubs
  - a FastAPI TestClient
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.db.database import VectorDBContext
from src.lg_workflow_agent import WorkflowAgent
from src.pipeline.orchestrator import ResearchPipeline


# ---------------------------------------------------------------------------
# DB stub — always in-memory, no external Qdrant
# ---------------------------------------------------------------------------

@pytest.fixture()
def in_memory_db() -> VectorDBContext:
    """VectorDBContext backed by an in-memory Qdrant instance."""
    with patch.dict(
        "os.environ",
        {"QDRANT_URL": "", "GOOGLE_API_KEY": "test-key", "AUTH_DISABLED": "true"},
        clear=False,
    ):
        # Patch embeddings so we never hit the Google API
        with patch(
            "src.db.database.GoogleGenerativeAIEmbeddings.embed_query",
            return_value=[0.1] * 3072,
        ):
            db = VectorDBContext()
            db.init_db()
            yield db


# ---------------------------------------------------------------------------
# Agent stub — returns a pre-made report without calling Gemini
# ---------------------------------------------------------------------------

FAKE_REPORT = "# Test Report\n\nThis is a mocked research report."


@pytest.fixture()
def mock_agent() -> WorkflowAgent:
    """WorkflowAgent whose invoke() returns a canned report instantly."""
    agent = WorkflowAgent.__new__(WorkflowAgent)
    agent.db = MagicMock()
    # Mock the graph builder and graph for the refactored architecture
    agent._builder = MagicMock()
    agent._graph = MagicMock()
    agent._builder.invoke.return_value = {"final_report": FAKE_REPORT}
    agent._builder.astream = MagicMock()
    # Mark as ready since we've set up the graph
    return agent


# ---------------------------------------------------------------------------
# Full pipeline wired with stubs
# ---------------------------------------------------------------------------

@pytest.fixture()
def pipeline(in_memory_db, mock_agent) -> ResearchPipeline:
    """ResearchPipeline using in-memory DB and mock agent."""
    p = ResearchPipeline(db=in_memory_db, agent=mock_agent)
    return p


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest.fixture()
def api_client(pipeline) -> TestClient:
    """TestClient whose pipeline singleton is replaced with our stub pipeline."""
    import src.api.server as server_module

    original_pipeline = server_module.pipeline
    server_module.pipeline = pipeline
    pipeline.initialize()

    client = TestClient(server_module.app)
    yield client

    server_module.pipeline = original_pipeline
