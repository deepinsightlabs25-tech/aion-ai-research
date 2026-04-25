# AI Report Gen v0.2.1

An AI-powered research agent built with FastAPI, LangChain / LangGraph, and Qdrant. The system accepts user queries, checks a vector-based RAG cache for prior results, and — on a cache miss — fires an async streaming Gemini ReAct agent that emits step-by-step progress updates as it gathers data from multiple external sources.

---

## Features

| Feature | Description |
|---|---|
| **Streaming Agent Progress** | `POST /query` returns immediately with a `task_id`. Poll `GET /status` to see each agent step (`model`, `tools`, …) appear in real time via the `steps[]` array. |
| **RAG Pre-caching** | Semantic similarity search (cosine >= 0.85) in Qdrant avoids redundant inference for previously researched topics. |
| **Multi-Source Fetcher** | Custom `fetch_trends` tool queries Hackernews, GitHub, Reddit, YouTube, Arxiv, RSS, Google News, and LinkedIn via an external MCP. |
| **LangChain + Gemini** | `gemini-2.5-flash` powers a ReAct graph; both sync `invoke()` and async `astream()` are supported. |
| **FastAPI Async** | `/query` is an `async def` route; streaming tasks run as `asyncio.create_task()` on the same event loop — no thread-pool blocking. |

---

## Documentation and Architecture
Full system design, component diagrams, request lifecycle, and streaming flow:  
**[Architecture Documentation](docs/architecture.md)**

---

## Testing

| Test | Purpose |
|---|---|
| [`tests/test_agent.py`](tests/test_agent.py) | Unit tests for `ResearchAgent` |
| [`tests/test_pipeline.py`](tests/test_pipeline.py) | Unit tests for `ResearchPipeline` |
| [`tests/test_streaming.py`](tests/test_streaming.py) | Async streaming integration tests — direct `astream()` + HTTP poll flow |
| [`tests/component_checks.ipynb`](tests/component_checks.ipynb) | Interactive notebook for DB / Agent / Pipeline component checks |
| [`tests/streamlit_app.py`](tests/streamlit_app.py) | **Real-time Testing Dashboard** — Visual interface for monitoring agent progress |

### Running Tests
Run all automated tests:
```bash
uv run pytest tests/
```

Run the streaming integration test against a live server:
```bash
uv run python tests/test_streaming.py
```

### Testing Dashboard
For a visual way to test the endpoints and monitor the agent's step-by-step progress, use the Streamlit application:

```bash
uv run streamlit run tests/streamlit_app.py
```
Note: Ensure the FastAPI server is running before launching the dashboard.

---

## Setup and Installation

This project uses [uv](https://github.com/astral-sh/uv) for fast dependency management.

### 1. Install uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Sync dependencies
```bash
uv sync
```

### 3. Environment variables
Copy `.env.example` to `.env` and fill in your keys:
```env
GOOGLE_API_KEY="your-google-genai-key"
QDRANT_API_KEY="your-qdrant-key"
QDRANT_URL="https://your-qdrant-cluster-url.com"
DEEP_AGENT_MODEL="google_genai:gemini-2.5-flash"
```

> **Note:** Omitting `QDRANT_URL` / `QDRANT_API_KEY` falls back to an in-memory Qdrant instance — useful for local development.

---

## Running the Server

```bash
uv run run.py
# or
uv run uvicorn src.api.server:app --reload
```

Binds to `http://localhost:8000`. Interactive documentation at `http://localhost:8000/docs`.

---

## API Endpoints

### `POST /query`
Submit a research query. Returns a cached report immediately, or a `task_id` for a new async job.

```json
// Request
{ "query": "research on machine learning" }

// Response (cache miss — streaming task started)
{ "status": "processing", "task_id": "9101e064-..." }

// Response (cache hit)
{ "status": "found", "report": "## Machine Learning..." }
```

### `GET /status?task_id=<id>`
Poll progress of an async research task. The `steps` array grows in real time as each agent node completes.

```json
{
  "status": "processing",          // pending | processing | completed | failed
  "steps": [
    { "step": "model", "content": "" },
    { "step": "tools", "content": "{\"results\": [{\"title\": \"HuggingFace...\"" },
    { "step": "model", "content": "## Research Report: Machine Learning Trends..." }
  ],
  "report": null,
  "error": null
}
```

### `GET /report`
Fetch all cached reports from Qdrant.

### `POST /cleanup`
Wipe the Qdrant collection and all in-memory task state.

### `GET /health`
Liveness check — returns `{"status": "ok"}`.

---

## Project Structure

```text
ai-report-gen/
├── pyproject.toml              # uv project config & dependencies
├── run.py                      # Entry point
├── .env / .env.example
├── docs/
│   └── architecture.md         # Full architecture details
├── tests/
│   ├── test_agent.py           # Agent unit tests
│   ├── test_pipeline.py        # Pipeline unit tests
│   ├── test_streaming.py       # Streaming integration tests
│   ├── streamlit_app.py        # Testing dashboard
│   └── component_checks.ipynb  # Interactive notebook
└── src/
    ├── agent/
    │   ├── core.py             # ResearchAgent — invoke() + astream()
    │   ├── prompts.py          # ReAct system prompt
    │   └── tools.py            # fetch_trends MCP tool
    ├── api/
    │   ├── models.py           # Pydantic schemas
    │   └── server.py           # FastAPI routes
    ├── pipeline/
    │   └── orchestrator.py     # ResearchPipeline orchestration
    └── db/
        └── database.py         # Qdrant persistence layer
```
