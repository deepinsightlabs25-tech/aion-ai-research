# LG Workflow Agent — Architecture & Flow

Complete architecture reference for the **LangGraph multi-agent research workflow** (`src/lg_workflow_agent/`).

---

## 1. High-Level Graph Flow

```mermaid
flowchart TD
    START(["▶ START"])

    CLASSIFY["🏷️ Classifier<br/><i>Determines query type</i>"]
    TASKGEN["📋 Task Generator<br/><i>Decomposes query into<br/>role-tagged subtasks</i>"]

    subgraph FAN_OUT ["⚡ Parallel Fan-Out via Send()"]
        direction LR
        DC["🔬 Data Collection<br/>Agent"]
        STATS["📊 Statistics<br/>Agent"]
        CITE["📚 Citation<br/>Agent"]
        WR["🌐 Web Research<br/>Agent"]
        LNC["📰 Latest News<br/>Collection Agent"]
    end

    AGG["🔗 Aggregator<br/><i>Consolidates all sub-agent<br/>outputs into structured JSON</i>"]
    WRITER["✍️ Writer<br/><i>Produces final<br/>Markdown report</i>"]
    VALIDATOR["✅ Validator<br/><i>URL reachability +<br/>LLM relevance check</i>"]
    CLEANUP["🧹 Cleanup<br/><i>Persist report,<br/>drop intermediates</i>"]

    FINISH(["⏹ END"])

    START --> CLASSIFY
    CLASSIFY --> TASKGEN
    TASKGEN -->|"Send(role_agent, payload)"| DC
    TASKGEN -->|"Send(role_agent, payload)"| STATS
    TASKGEN -->|"Send(role_agent, payload)"| CITE
    TASKGEN -->|"Send(role_agent, payload)"| WR
    TASKGEN -->|"Send(role_agent, payload)"| LNC

    DC --> AGG
    STATS --> AGG
    CITE --> AGG
    WR --> AGG
    LNC --> AGG

    AGG --> WRITER
    WRITER --> VALIDATOR

    VALIDATOR -->|"VALID / FORCED_FINISH"| RF["🖼️ Report Finalizer<br/><i>Generates charts/images,<br/>embeds into report</i>"]
    VALIDATOR -->|"INVALID_REFS<br/>(rewrite loop, max 2 iterations)"| WRITER

    RF --> PW["📑 Paper Writer<br/><i>LaTeX → PDF<br/>(deep_research only;<br/>no-op for other types)</i>"]
    PW --> CLEANUP
    CLEANUP --> FINISH
```

---

## 2. Query-Type Role Mapping

The **Classifier** assigns one of four query types. Each type activates a different subset of sub-agents for the parallel fan-out:

```mermaid
flowchart LR
    Q["User Query"]

    Q --> C{"Classifier"}

    C -->|"deep_research"| DR["data_collection<br/>statistics<br/>citation"]
    C -->|"blog"| BL["web_research<br/>latest_news_collection"]
    C -->|"comparative"| CO["web_research<br/>latest_news_collection"]
    C -->|"summary"| SU["web_research<br/>latest_news_collection"]

    style DR fill:#e8f5e9,stroke:#388e3c
    style BL fill:#e3f2fd,stroke:#1976d2
    style CO fill:#fff3e0,stroke:#f57c00
    style SU fill:#fce4ec,stroke:#c62828
```

| Query Type | Activated Sub-Agents | Use Case |
|---|---|---|
| `deep_research` | `data_collection`, `statistics`, `citation` | Rigorous, citation-heavy investigation |
| `blog` | `web_research`, `latest_news_collection` | Informal/explanatory article |
| `comparative` | `web_research`, `latest_news_collection` | Compare/contrast entities or tools |
| `summary` | `web_research`, `latest_news_collection` | Short factual digest or overview |

---

## 3. Detailed Node-by-Node Flow

```mermaid
sequenceDiagram
    participant U as User / API
    participant CL as Classifier
    participant TG as Task Generator
    participant SA as Sub-Agents (parallel)
    participant AG as Aggregator
    participant WR as Writer
    participant VA as Validator
    participant RF as Report Finalizer
    participant PW as Paper Writer
    participant CU as Cleanup
    participant DB as Qdrant DB

    U->>CL: query + task_id
    CL->>CL: LLM classifies → query_type + rationale
    CL-->>DB: persist(classify)
    CL->>TG: {query_type}

    TG->>TG: LLM decomposes → subtasks[]
    TG-->>DB: persist(task_generation)
    TG->>SA: Send() fan-out per subtask

    par Parallel Execution
        SA->>SA: data_collection / statistics / citation
        SA->>SA: web_research / latest_news_collection
    end
    Note over SA: Each sub-agent uses fetch_* source tools + think_tool

    SA->>AG: worker_outputs[] (merged via add reducer)

    AG->>AG: LLM consolidates → {sections, references, metadata}
    AG-->>DB: persist(aggregation)
    AG->>WR: {aggregated}

    WR->>WR: LLM writes Markdown report
    WR-->>DB: persist(draft)
    WR->>VA: {draft_report}

    loop Validation (max 2 rewrites)
        VA->>VA: HEAD/GET each URL → reachability
        VA->>VA: LLM relevance scoring per reference
        alt All references valid
            VA->>RF: validated report + aggregated data
            RF->>RF: generate charts, render images, embed into report
            RF->>PW: report_with_charts
            PW->>PW: if deep_research → LaTeX → PDF (compile retry x3)
            PW->>CU: final_report + paper artifacts
        else Broken / irrelevant refs found
            VA->>WR: invalid_references[] → rewrite
            WR->>VA: revised draft_report
        end
    end

    CU->>DB: save_report(query, final_report)
    CU->>DB: cleanup_task_data(task_id)
    CU-->>U: final_report (+ pdf_base64 for deep_research)
```

---

## 4. State Schema

All data flows through a single `WorkflowState` (TypedDict). Key fields and their reducers:

```mermaid
classDiagram
    class WorkflowState {
        +query : str
        +task_id : str
        +messages : Annotated[list, add_messages]
        +query_type : "blog" | "comparative" | "deep_research" | "summary"
        +classification_rationale : str
        +subtasks : list~dict~
        +worker_payloads : list~dict~
        +worker_outputs : Annotated[list~dict~, operator.add]
        +aggregated : dict
        +draft_report : str
        +final_report : str
        +chart_specs : list
        +report_images : list~dict~
        +validation_feedback : str
        +invalid_references : list~str~
        +rewrite_iterations : int
        +research_paper_latex : str
        +research_paper_metadata : dict
        +research_paper_pdf_base64 : str | None
    }

    note for WorkflowState "worker_outputs uses operator.add reducer; parallel Send() results are appended, not overwritten"
```

| Field | Set By | Consumed By |
|---|---|---|
| `query`, `task_id`, `messages` | Initial input | All nodes |
| `query_type`, `classification_rationale` | Classifier | Task Generator, Aggregator, Validator |
| `subtasks`, `worker_payloads` | Task Generator | Assign Workers (fan-out) |
| `worker_outputs` | Sub-agents (additive) | Aggregator |
| `aggregated` | Aggregator | Writer, Validator |
| `draft_report` | Writer | Validator |
| `final_report` | Validator / Report Finalizer | Paper Writer, Cleanup, API response |
| `chart_specs` | Report Finalizer | Report Finalizer / Cleanup |
| `report_images` | Report Finalizer | Cleanup / persisted report payload |
| `invalid_references`, `rewrite_iterations` | Validator | Writer (rewrite loop) |
| `research_paper_latex` | Paper Writer | Cleanup / persisted payload |
| `research_paper_metadata` | Paper Writer | Cleanup / persisted payload |
| `research_paper_pdf_base64` | Paper Writer | API response (`/status`) for deep_research queries |

> Note: The `Report Finalizer` node enriches validated drafts with auto-generated charts and embedded image assets. For `deep_research` queries, the downstream `Paper Writer` then produces a LaTeX manuscript that is compiled to PDF (returned as base64 in `research_paper_pdf_base64`). For all other query types the paper writer is a no-op.

---

## 5. Sub-Agent Architecture

Each sub-agent is a pre-built `create_agent` instance constructed **once** at graph-build time and reused across all invocations.

```mermaid
flowchart TD
    subgraph BUILD_TIME ["Graph Build Time (once)"]
        LLM["ChatGoogleGenerativeAI<br/>(gemini-2.5-flash)"]
        TOOLS["Tools:<br/>fetch_* (9 sources)<br/>think_tool"]
        BUILD["build_sub_agents(llm, tools)"]

        LLM --> BUILD
        TOOLS --> BUILD

        BUILD --> A1["data_collection_agent"]
        BUILD --> A2["statistics_agent"]
        BUILD --> A3["citation_agent"]
        BUILD --> A4["web_research_agent"]
        BUILD --> A5["latest_news_collection_agent"]
    end

    subgraph RUN_TIME ["Per-Invocation (lightweight runner)"]
        P["payload:<br/>{query, task, subtask_id, role}"]
        R["runner(payload)<br/>→ agent.invoke()"]
        O["worker_outputs:<br/>[{subtask_id, role, task, output}]"]

        P --> R --> O
    end

    A1 -.->|"pre-built"| R
    A2 -.->|"pre-built"| R
    A3 -.->|"pre-built"| R
    A4 -.->|"pre-built"| R
    A5 -.->|"pre-built"| R
```

### Sub-Agent Responsibilities

| Agent | System Prompt Focus | Output Format |
|---|---|---|
| **Data Collection** | Primary facts from authoritative sources | `## Findings` + `## Sources` |
| **Statistics** | Quantitative data, benchmarks, growth rates | `## Key Statistics` + `## Analysis` + `## Sources` |
| **Citation** | High-quality references (papers, docs, standards) | `## References` with one-line notes |
| **Web Research** | Diverse current web information | `## Findings` + `## Sources` |
| **Latest News Collection** | Recent news links + short snippets only | `## Latest News` bullet list (5-10 items, no prose) |

---

## 6. Validation & Rewrite Loop

The Validator performs a two-axis check on every reference in the draft:

```mermaid
flowchart TD
    DRAFT["Draft Report<br/>(from Writer)"]

    DRAFT --> EXTRACT["Extract references<br/>from aggregated + draft URLs"]

    EXTRACT --> URL_CHECK["Axis 1: URL Reachability<br/>HEAD / GET each URL"]
    URL_CHECK --> BROKEN["Broken URLs"]
    URL_CHECK --> LIVE["Live URLs"]

    LIVE --> LLM_CHECK["Axis 2: LLM Relevance<br/>Score each ref against<br/>query + subtasks"]
    LLM_CHECK --> IRRELEVANT["Irrelevant URLs"]
    LLM_CHECK --> RELEVANT["Relevant URLs"]

    BROKEN --> INVALID["Combined Invalid Set<br/>(broken + irrelevant)"]
    IRRELEVANT --> INVALID

    INVALID --> DECISION{Any invalid?}
    RELEVANT --> DECISION

    DECISION -->|"No"| VALID["✅ VALID<br/>→ Cleanup"]
    DECISION -->|"Yes, iterations < 2"| REWRITE["🔄 REWRITE<br/>→ Writer with<br/>invalid_references[]"]
    DECISION -->|"Yes, iterations ≥ 2"| FORCED["⚠️ FORCED_FINISH<br/>Replace invalid URLs<br/>with placeholder"]

    REWRITE --> DRAFT
```

---

## 7. Tools

Each sub-agent has direct access to one source-fetching tool per supported platform plus a reflection tool. All fetchers are **native async** — they call the underlying source API directly (no external MCP server in the loop):

```mermaid
flowchart LR
    subgraph TOOLS ["Available Tools (LangChain @tool)"]
        FH["fetch_hackernews"]
        FY["fetch_youtube"]
        FG["fetch_github"]
        FL["fetch_linkedin"]
        FR["fetch_reddit"]
        FS["fetch_rss"]
        FN["fetch_google_news"]
        FP["fetch_podcasts"]
        FA["fetch_arxiv"]
        TT["think_tool<br/>(reflection)"]
    end

    subgraph SOURCES ["src/lg_workflow_agent/sources/"]
        S1["hackernews.py"]
        S2["youtube.py"]
        S3["github.py"]
        S4["linkedin.py"]
        S5["reddit.py"]
        S6["rss.py"]
        S7["google_news.py"]
        S8["podcast.py"]
        S9["arxiv.py"]
    end

    FH --> S1
    FY --> S2
    FG --> S3
    FL --> S4
    FR --> S5
    FS --> S6
    FN --> S7
    FP --> S8
    FA --> S9

    S1 -->|httpx| HN["Hacker News API"]
    S2 -->|httpx| YT["YouTube"]
    S3 -->|httpx| GH["GitHub API"]
    S4 -->|httpx| GS["Google search"]
    S5 -->|httpx| RD["Reddit"]
    S6 -->|feedparser| RSS["RSS feeds"]
    S7 -->|httpx| GN["Google News"]
    S8 -->|httpx| PC["Podcast directories"]
    S9 -->|httpx| AX["arXiv API"]
```

Each fetcher returns a Pydantic `SourceResult` serialised to JSON for the LLM. The active set of tools is identical across sub-agents; prompts steer which sources are appropriate per role.

Additionally, the **Validator node** uses internal URL-checking utilities (not agent tools):
- `extract_urls(text)` — regex extraction of HTTP/HTTPS URLs from text
- `validate_url(url)` — HEAD/GET reachability check
- `validate_urls(urls)` — batch validation returning `{url: bool}`

And the **Paper Writer node** uses LaTeX utilities from `paper_formatter.py`:
- `clean_latex(text)` — strip stray markdown / artefacts
- `validate_latex(text)` — structural sanity check
- `compile_latex_to_pdf(text)` — `pdflatex` invocation with error capture
- `extract_paper_metadata(text)` — title/abstract/word-count extraction
- `pdf_to_base64(path)` — final encoding for API transport

---

## 8. Module Map

```
src/lg_workflow_agent/
├── __init__.py          # Public API exports: WorkflowAgent, WorkflowGraphBuilder, WorkflowState
├── agent.py             # WorkflowAgent — top-level entry point (build, invoke, astream)
├── graph.py             # WorkflowGraphBuilder — LangGraph StateGraph construction
├── nodes.py             # Node factories (classifier, task_gen, sub-agent runners, aggregator,
│                       #                writer, validator, report_finalizer, paper_writer, cleanup)
├── prompts.py           # All LLM prompt templates
├── state.py             # WorkflowState TypedDict with reducer annotations
├── sub_agents.py        # build_sub_agents() + build_role_runners() factories
├── tools.py             # @tool fetchers + URL validation utilities
├── chart_generator.py   # matplotlib renderers for 12+ chart/diagram types → base64 PNG
├── paper_formatter.py   # LaTeX cleaning, validation, pdflatex compilation, PDF → base64
├── run_sample.py        # Standalone sample script
└── sources/             # Direct async source fetchers (no MCP)
    ├── arxiv.py
    ├── github.py
    ├── google_news.py
    ├── hackernews.py
    ├── linkedin.py
    ├── podcast.py
    ├── reddit.py
    ├── rss.py
    ├── youtube.py
    ├── _config.py       # Shared HTTP config (timeouts, headers, retries)
    ├── _feed_utils.py   # RSS/feed helpers
    └── _models.py       # SourceResult Pydantic schema
```

---

## 9. Integration with the Wider System

```mermaid
flowchart TD
    CLIENT["Client / Streamlit UI"]
    API["FastAPI Server<br/>(src/api/server.py)"]
    PIPE["ResearchPipeline<br/>(src/pipeline/orchestrator.py)"]
    WFA["WorkflowAgent<br/>(src/lg_workflow_agent/agent.py)"]
    GRAPH["LangGraph Compiled<br/>(src/lg_workflow_agent/graph.py)"]
    DB["Qdrant Vector DB<br/>(src/db/database.py)"]

    CLIENT -->|"POST /query"| API
    API --> PIPE
    PIPE -->|"cache check"| DB
    PIPE -->|"cache miss → astream()"| WFA
    WFA --> GRAPH
    GRAPH -->|"intermediate persist"| DB
    GRAPH -->|"final save_report()"| DB
    PIPE -->|"steps[] polling"| API
    API -->|"GET /status"| CLIENT

    style GRAPH fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style WFA fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
```

The `WorkflowAgent` is the sole research runtime exposed to the pipeline. It compiles the LangGraph once at startup and exposes the standard `build()` / `invoke(query)` / `astream(query)` interface used by `ResearchPipeline`. The workflow decomposes the query into parallel specialized sub-agents before producing the final report, then enriches it with charts and (for deep research) a compiled LaTeX PDF.

---

## 10. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Fan-out via `Send()`** | LangGraph's `Send` dispatches sub-agents in parallel; `worker_outputs` uses `Annotated[list, operator.add]` so results are appended, never overwritten |
| **Latest News Collection (not Content Drafting)** | The drafting role was running in parallel with research, producing prose without data. Replaced with a focused news-link collector; actual prose is written by the downstream **Writer** node which has access to all aggregated data |
| **Two-axis validation** | URL reachability alone isn't sufficient — an accessible but off-topic page is equally harmful. LLM relevance scoring catches fabricated or tangential references |
| **Max 2 rewrites** | Prevents infinite loops when the LLM keeps generating bad references. After 2 rewrites, invalid URLs are replaced with `[invalid link removed]` |
| **Sub-agents built once** | `create_agent` is called at graph-build time, not per-invocation. Runners are lightweight closures that just call `.invoke()` on the pre-built agent |
| **Direct source fetchers (no MCP)** | Each source now has a native async module under `sources/`. Eliminating the MCP hop removes a network round-trip per tool call, a deployment dependency, and a class of timeout / cold-start failures |
| **Paper writer is a single node, not a sub-graph** | The LaTeX compile-fix loop happens inside `node_paper_writer` (up to 3 attempts with an LLM-driven fix prompt). Keeping it as a single node avoids polluting the public graph topology with deep-research-only edges |
| **Best-effort persistence** | `_persist()` wraps all DB writes in try/except so a Qdrant or Postgres outage never breaks the workflow |