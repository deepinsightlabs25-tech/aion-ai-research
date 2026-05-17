# Aion AI Research — Backend

A FastAPI + LangGraph multi-agent research backend. The system accepts user queries, checks a Qdrant RAG cache for prior results, and — on a cache miss — runs an async streaming **LangGraph workflow** that fans out to specialized sub-agents (data collection, statistics, citation, web research, latest news), aggregates their findings, drafts a Markdown report, validates references, finalizes charts/images, and (for deep-research queries) compiles a LaTeX research paper to PDF.

---

## Features

| Feature | Description |
|---|---|
| **Multi-Agent Workflow** | LangGraph state machine: `classifier → task_generator → parallel sub-agents (Send fan-out) → aggregator → writer → validator ↻ → report_finalizer → paper_writer → cleanup`. |
| **Streaming Progress** | `POST /query` returns immediately with a `task_id`. Poll `GET /status` to see each LangGraph node completion (`classifier`, `aggregator`, `writer`, …) stream into `steps[]` in real time. |
| **RAG Pre-caching** | Semantic similarity search (cosine ≥ 0.85) in Qdrant avoids redundant inference for previously researched topics. |
| **Direct Source Fetchers** | Native-async tools (`fetch_hackernews`, `fetch_youtube`, `fetch_github`, `fetch_linkedin`, `fetch_reddit`, `fetch_rss`, `fetch_google_news`, `fetch_podcasts`, `fetch_arxiv`) call source APIs directly — no external MCP hop. |
| **Validator with Rewrite Loop** | Each reference is checked for URL reachability **and** LLM-scored relevance. Up to 2 rewrite passes; otherwise broken refs are stripped. |
| **Chart + Paper Generation** | `report_finalizer` produces 12+ visualization types (bar, line, heatmap, flowchart, architecture, equation, …); `paper_writer` converts deep-research reports to a LaTeX academic paper compiled to PDF. |
| **Supabase Postgres** | Per-user task tracking, history, and step persistence alongside the Qdrant vector cache. |
| **Gemini 2.5 Flash** | `gemini-2.5-flash` powers all sub-agents, the classifier, writer, validator, and paper generator. |

---

## Documentation

| Doc | Contents |
|---|---|
| **[docs/architecture.md](docs/architecture.md)** | High-level system design, request lifecycle, component map, streaming flow. |
| **[docs/LANGGRAPH_WORKFLOW.md](docs/LANGGRAPH_WORKFLOW.md)** | Full reference for the multi-agent LangGraph workflow — graph topology, sub-agents, state schema, validation loop, paper generation. |
| **[docs/ENHANCED_VISUALIZATIONS.md](docs/ENHANCED_VISUALIZATIONS.md)** | Catalog of all chart/diagram types produced by `report_finalizer`. |
| **[docs/USAGE_GUIDE.md](docs/USAGE_GUIDE.md)** | End-to-end usage examples for the HTTP API. |

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
GOOGLE_CLIENT_ID="your-google-oauth-client-id"
QDRANT_API_KEY="your-qdrant-key"
QDRANT_URL="https://your-qdrant-cluster-url.com"
DEEP_AGENT_MODEL="google_genai:gemini-2.5-flash"
# Local testing only. Keep false in deployed environments.
AUTH_DISABLED="false"
CORS_ORIGINS="https://ai-report-gen.onrender.com,http://localhost:5175,https://deepinsightlabs25-tech.github.io"
```

> **Note:** Omitting `QDRANT_URL` / `QDRANT_API_KEY` falls back to an in-memory Qdrant instance — useful for local development.
> For Google Sign-In, use the OAuth **Web Client ID**. Do not expose or use `client_secret` in frontend code.

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
Requires `Authorization: Bearer <google_id_token>`.

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
Requires `Authorization: Bearer <google_id_token>`.

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
Requires `Authorization: Bearer <google_id_token>`.

### `POST /cleanup`
Wipe the Qdrant collection and all in-memory task state.
Requires `Authorization: Bearer <google_id_token>`.

### `GET /auth/me`
Validates the bearer token and returns the signed-in user profile.

### `GET /health`
Liveness check — returns `{"status": "ok"}`.

---

## Project Structure

```text
backend/
├── pyproject.toml              # uv project config & dependencies
├── run.py                      # Entry point (uvicorn launcher)
├── .env / .env.example
├── docs/
│   ├── architecture.md         # High-level system architecture
│   ├── LANGGRAPH_WORKFLOW.md   # Multi-agent workflow reference
│   ├── ENHANCED_VISUALIZATIONS.md
│   └── USAGE_GUIDE.md
├── tests/
│   ├── test_agent.py           # WorkflowAgent unit tests
│   ├── test_pipeline.py        # Pipeline unit tests
│   ├── test_streaming.py       # Streaming integration tests
│   ├── test_sources.py         # Source fetcher tests
│   ├── test_enhanced_visualizations.py
│   ├── streamlit_app.py        # Testing dashboard
│   └── component_checks.ipynb  # Interactive notebook
└── src/
    ├── api/
    │   ├── auth.py             # Google OAuth bearer-token validation
    │   ├── models.py           # Pydantic request/response schemas
    │   └── server.py           # FastAPI routes (/query, /status, /report, …)
    ├── pipeline/
    │   └── orchestrator.py     # ResearchPipeline — cache + task store + astream loop
    ├── lg_workflow_agent/
    │   ├── agent.py            # WorkflowAgent — build / invoke / astream entry point
    │   ├── graph.py            # LangGraph StateGraph construction
    │   ├── nodes.py            # Node factories (classifier, writer, validator, finalizer, paper_writer, …)
    │   ├── sub_agents.py       # create_agent instances per role + runner closures
    │   ├── state.py            # WorkflowState TypedDict + reducers
    │   ├── prompts.py          # All LLM prompt templates
    │   ├── tools.py            # Source tools (@tool) + URL validation utilities
    │   ├── chart_generator.py  # 12+ matplotlib chart renderers → base64 PNG
    │   ├── paper_formatter.py  # LaTeX cleanup, validation, PDF compilation
    │   └── sources/            # Direct async fetchers (arxiv, github, reddit, …)
    └── db/
        ├── database.py         # Qdrant vector cache
        ├── postgres.py         # Supabase Postgres task tracking
        └── supabase_client.py  # Supabase REST client wrapper
```
