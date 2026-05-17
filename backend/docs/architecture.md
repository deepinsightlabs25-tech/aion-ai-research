# System Architecture & Flow

This document describes the high-level architecture of the **Aion AI Research** backend: the FastAPI API layer, the `ResearchPipeline` orchestrator, the `WorkflowAgent` LangGraph multi-agent runtime, the dual persistence layers (Qdrant + Supabase Postgres), and the streaming progress design.

For the full reference of the multi-agent LangGraph workflow itself (nodes, sub-agents, validation loop, paper generation), see [LANGGRAPH_WORKFLOW.md](LANGGRAPH_WORKFLOW.md).

---

## High-Level Architecture

```mermaid
graph TD
    User(["👤 User / Frontend"])
    API["🌐 FastAPI Layer<br/>(src/api/server.py)"]
    Auth["🔐 Google OAuth Bearer<br/>(src/api/auth.py)"]
    Orch["🔀 ResearchPipeline<br/>(src/pipeline/orchestrator.py)"]
    Qdrant[("🧠 Qdrant Vector Cache<br/>(src/db/database.py)")]
    PG[("🗃️ Supabase Postgres<br/>(src/db/postgres.py)")]
    Agent["🤖 WorkflowAgent<br/>(src/lg_workflow_agent/agent.py)"]
    Graph["🕸️ LangGraph StateGraph<br/>(src/lg_workflow_agent/graph.py)"]
    Sources["🌍 Direct Source APIs<br/>(arxiv, github, reddit, youtube,<br/>hackernews, rss, news, podcasts, linkedin)"]

    User -- "Authorization: Bearer <id_token>" --> API
    API --> Auth
    API -- "process_query()" --> Orch
    Orch -- "semantic search" --> Qdrant
    Orch -- "task lifecycle / history" --> PG

    Qdrant -- "cache HIT → report" --> Orch
    Orch -- "cache HIT → status:found" --> API
    API -- "200 + report" --> User

    Orch -- "cache MISS → task_id" --> API
    API -- "200 + task_id\nasyncio.create_task()" --> User

    subgraph "🔄 Async Streaming Background Task"
        Orch -- "astream(query)" --> Agent
        Agent --> Graph
        Graph -- "fetch_* tools" --> Sources
        Sources -- "trend data" --> Graph
        Graph -- "step update / state" --> Agent
        Agent -- "yield {step, content, data}" --> Orch
        Orch -- "append to steps[]" --> Orch
        Orch -- "save_report()" --> Qdrant
        Orch -- "update task" --> PG
    end

    User -- "GET /status?task_id=..." --> API
    API -- "steps[], status, report" --> User
```

---

## Streaming Agent Progress Flow

When the cache misses, `/query` schedules a **non-blocking async task** that iterates `WorkflowAgent.astream()` and appends every LangGraph node completion to an in-memory task record. Clients poll `/status` to watch `steps[]` grow.

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI /query
    participant Orch as ResearchPipeline
    participant Agent as WorkflowAgent
    participant LG as LangGraph (classifier→…→cleanup)
    participant SRC as Source APIs
    participant Q as Qdrant
    participant PG as Postgres

    C->>API: POST /query {"query": "..."}
    API->>Orch: process_query()
    Orch->>Q: semantic_search()
    Q-->>Orch: no match (cache miss)
    Orch->>PG: record_research_task()
    Orch-->>API: {status:"processing", task_id}
    API-->>C: 200 {task_id}

    Note over API,Agent: asyncio.create_task(run_task_streaming)

    loop Each LangGraph node completion
        Agent->>LG: astream(initial_state)
        LG->>SRC: fetch_hackernews / arxiv / github / …
        SRC-->>LG: JSON results
        LG-->>Agent: state update per node
        Agent-->>Orch: {step:"step: <node>", content, data}
        Orch->>PG: persist step (best-effort)
    end

    LG-->>Agent: final_report (+ paper, charts)
    Agent-->>Orch: final state
    Orch->>Q: save_report(query, report)
    Orch->>PG: mark task completed

    loop Polling
        C->>API: GET /status?task_id
        API-->>C: {status, steps[], report?, paper?}
    end
```

---

## Component Interaction Map

```mermaid
classDiagram
    class FastAPI {
        +startup_event()
        +create_query(request) QueryResponse
        +get_status(task_id) TaskStatusResponse
        +get_all_reports() ReportListResponse
        +cleanup_db() dict
        +auth_me() AuthUserResponse
        +health() HealthResponse
    }

    class ResearchPipeline {
        +db: VectorDBContext
        +agent: WorkflowAgent
        -_tasks: _EvictingTaskStore
        +initialize()
        +process_query(query) dict
        +run_task_streaming(task_id, query)
        +get_task_status(task_id) dict
        +get_all_reports() list
        +cleanup()
    }

    class WorkflowAgent {
        -_builder: WorkflowGraphBuilder
        -_graph: CompiledGraph
        +is_ready bool
        +build()
        +invoke(query) str
        +astream(query) AsyncGenerator
    }

    class WorkflowGraphBuilder {
        +llm
        +db
        +build() CompiledGraph
        +invoke(initial_state) dict
        +astream(initial_state) AsyncGenerator
    }

    class VectorDBContext {
        +init_db()
        +search_query(query) str
        +save_report(query, report)
        +get_reports() list
        +cleanup()
    }

    class PostgresDB {
        +create_tables()
        +record_research_task(...)
        +append_task_step(...)
        +update_task_status(...)
        +list_tasks_for_user(...)
    }

    class TaskStatusResponse {
        +status: str
        +report: str | None
        +error: str | None
        +steps: list
        +research_paper_pdf_base64: str | None
    }

    FastAPI --> ResearchPipeline : delegates all logic
    ResearchPipeline --> WorkflowAgent : astream()
    WorkflowAgent --> WorkflowGraphBuilder : compiles LangGraph
    ResearchPipeline --> VectorDBContext : cache lookup & save
    ResearchPipeline --> PostgresDB : task lifecycle
    FastAPI ..> TaskStatusResponse : returns from /status
```

---

## Data Flow — Cache Hit vs Miss

```mermaid
flowchart LR
    Q["🔍 Incoming Query"] --> SEM["Semantic Search<br/>(Qdrant cosine ≥ 0.85)"]

    SEM -- "HIT" --> CACHED["📦 Return Cached Report<br/>status: found"]
    SEM -- "MISS" --> TASK["🆕 Create task_id<br/>status: processing"]

    TASK --> ASYNC["asyncio.create_task()<br/>run_task_streaming()"]

    ASYNC --> N1["classifier"]
    N1 --> N2["task_generator"]
    N2 --> N3["sub-agents (parallel Send)"]
    N3 --> N4["aggregator"]
    N4 --> N5["writer"]
    N5 --> N6["validator (↻ up to 2x)"]
    N6 --> N7["report_finalizer<br/>(charts/images)"]
    N7 --> N8["paper_writer<br/>(deep_research → LaTeX/PDF)"]
    N8 --> N9["cleanup"]

    N9 --> SAVE["💾 save_report()<br/>Qdrant vectorised"]
    SAVE --> DONE["✅ status: completed"]

    N1 -.-> STATUS["📊 GET /status<br/>steps growing…"]
    N5 -.-> STATUS
    N7 -.-> STATUS
    DONE -.-> STATUS
```

---

## Core Components

### 1. API Layer — `src/api/`

FastAPI application entry point.

- **`server.py`** — Route definitions. `/query` is `async def` so `asyncio.create_task()` runs on the event loop without blocking. CORS origins are configurable via `CORS_ORIGINS`.
- **`auth.py`** — Google OAuth bearer-token validation. Honors `AUTH_DISABLED=true` for local development.
- **`models.py`** — Pydantic request/response schemas, including `TaskStatusResponse.steps` and the optional `research_paper_pdf_base64` produced by deep-research runs.

### 2. Research Pipeline — `src/pipeline/orchestrator.py`

Stateful orchestration hub between the API, the DB layers, and the agent.

| Method | Purpose |
|---|---|
| `initialize()` | Lazily builds the `WorkflowAgent` and warms the Qdrant collection. |
| `process_query()` | Cache lookup. Returns either `{status:"found", report}` or `{status:"processing", task_id}`. |
| `run_task_streaming()` | Async — iterates `agent.astream()`, appends each step to `task["steps"]`, persists progress to Postgres, then saves the final report to Qdrant. |
| `get_task_status()` | Returns the live task dict polled by `/status`. |
| `_tasks` | Bounded `_EvictingTaskStore` (max 5 completed tasks, 10-minute TTL) to bound process memory. |

Memory hygiene: `_release_memory()` closes lingering matplotlib figures and runs a GC pass after each task to keep the chart generator from leaking pyplot state.

### 3. WorkflowAgent — `src/lg_workflow_agent/`

A **LangGraph multi-agent workflow** backed by `gemini-2.5-flash`.

| Method | Mode | Description |
|---|---|---|
| `build()` | Lifecycle | Instantiates the LLM and compiles the StateGraph once at startup. |
| `invoke(query)` | Sync | Blocking full run — returns final report string. |
| `astream(query)` | **Async generator** | Yields `{step, content, data}` after every LangGraph node completes (classifier, task_generator, each sub-agent, aggregator, writer, validator, report_finalizer, paper_writer, cleanup). |

The graph topology, sub-agent prompts, and validation logic are documented in [LANGGRAPH_WORKFLOW.md](LANGGRAPH_WORKFLOW.md). At a glance:

```
START → classifier → task_generator
      → [data_collection | statistics | citation | web_research | latest_news_collection]   (parallel Send fan-out)
      → aggregator → writer → validator ⤺ (rewrite ×0..2)
      → report_finalizer (charts/images) → paper_writer (LaTeX/PDF, deep_research only) → cleanup → END
```

### 4. Vector Database — `src/db/database.py`

A **Qdrant**-backed RAG cache.

- **Embeddings**: `models/gemini-embedding-001` → 3072-dimensional vectors.
- **Similarity**: Cosine distance, threshold 0.85.
- **Collection**: `research_reports`.
- **Fallback**: When `QDRANT_URL` is unset, an in-memory Qdrant instance is used (useful for local development and CI).

### 5. Supabase Postgres — `src/db/postgres.py`, `src/db/supabase_client.py`

Relational layer for **per-user task lifecycle**:

- Records each research task with `task_id`, `user_id`, query, timestamps.
- Appends step-level progress so the workflow can be inspected after the in-memory task has been evicted.
- Powers the user's history view in the frontend.

All Postgres writes are best-effort — failures are logged but do not break the agent run.

### 6. Source Fetchers — `src/lg_workflow_agent/sources/`

Each source has a small async module that hits its native API and returns a Pydantic `SourceResult`:

`arxiv` · `github` · `google_news` · `hackernews` · `linkedin` (via Google search) · `podcast` · `reddit` · `rss` · `youtube`

These are wrapped as LangChain `@tool`s in `src/lg_workflow_agent/tools.py` (`fetch_arxiv`, `fetch_github`, …) and exposed to every sub-agent. No external MCP hop is involved.

---

## Request Lifecycle (Detailed)

```mermaid
stateDiagram-v2
    [*] --> Received : POST /query

    Received --> CacheHit : cosine similarity ≥ 0.85
    Received --> CacheMiss : no similar query found

    CacheHit --> [*] : 200 {status: found, report}

    CacheMiss --> Pending : task_id created
    Pending --> Processing : asyncio.create_task() fires
    Processing --> Streaming : agent.astream() iterating

    state Streaming {
        [*] --> Classify : classifier
        Classify --> TaskGen : task_generator
        TaskGen --> SubAgents : Send fan-out
        SubAgents --> Aggregate : aggregator
        Aggregate --> Draft : writer
        Draft --> Validate : validator
        Validate --> Draft : rewrite (max 2x)
        Validate --> Finalize : valid / forced_finish
        Finalize --> Paper : report_finalizer → paper_writer
        Paper --> [*] : cleanup
    }

    Streaming --> Completed : report saved to Qdrant
    Streaming --> Failed : exception caught

    Completed --> [*] : GET /status → {status: completed, report, paper?}
    Failed --> [*] : GET /status → {status: failed, error}
```

---

## Testing Strategy

| Layer | Files | Coverage |
|---|---|---|
| Unit | `tests/test_agent.py`, `tests/test_pipeline.py`, `tests/test_postgres_tasks.py` | Agent build/invoke mocks, pipeline state machine, Postgres CRUD |
| Sources | `tests/test_sources.py` | Each direct source fetcher (mocked HTTP) |
| Streaming | `tests/test_streaming.py` | Direct `astream()` + full HTTP poll flow |
| Visualizations | `tests/test_enhanced_visualizations.py`, `tests/test_visualization_integration.py` | Chart generator + finalizer integration |
| API | `tests/test_api.py`, `tests/smoke_test_api.py` | FastAPI routes, auth, status polling |
| Interactive | `tests/component_checks.ipynb`, `tests/lg_workflow_agent_checks.ipynb` | Manual exploration notebooks |
| Dashboard | `tests/streamlit_app.py` | Visual progress monitor over the live API |

```bash
# All unit tests
uv run pytest tests/

# Streaming integration (requires live server)
uv run python tests/test_streaming.py

# Visual dashboard
uv run streamlit run tests/streamlit_app.py
```

See the [tests/](../tests/) directory for full details.
