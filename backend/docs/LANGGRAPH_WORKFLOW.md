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

    VALIDATOR -->|"VALID / FORCED_FINISH"| CLEANUP
    VALIDATOR -->|"INVALID_REFS<br/>(rewrite loop, max 2 iterations)"| WRITER

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
    Note over SA: Each sub-agent uses fetch_trends + think_tool

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
            VA->>CU: final_report
        else Broken / irrelevant refs found
            VA->>WR: invalid_references[] → rewrite
            WR->>VA: revised draft_report
        end
    end

    CU->>DB: save_report(query, final_report)
    CU->>DB: cleanup_task_data(task_id)
    CU-->>U: final_report
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
        +validation_feedback : str
        +invalid_references : list~str~
        +rewrite_iterations : int
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
| `final_report` | Validator / Cleanup | API response |
| `invalid_references`, `rewrite_iterations` | Validator | Writer (rewrite loop) |

---

## 5. Sub-Agent Architecture

Each sub-agent is a pre-built `create_agent` instance constructed **once** at graph-build time and reused across all invocations.

```mermaid
flowchart TD
    subgraph BUILD_TIME ["Graph Build Time (once)"]
        LLM["ChatGoogleGenerativeAI<br/>(gemini-2.5-flash)"]
        TOOLS["Tools:<br/>fetch_trends<br/>think_tool"]
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

Both tools are shared across all sub-agents:

```mermaid
flowchart LR
    subgraph TOOLS ["Available Tools"]
        FT["fetch_trends<br/>(source, topic, limit, period)"]
        TT["think_tool<br/>(reflection)"]
    end

    subgraph EXTERNAL ["External"]
        MCP["Research MCP Server<br/>https://research-mcp-...onrender.com"]
    end

    FT -->|"POST /trends/{source}"| MCP
    TT -->|"Returns reflection<br/>(strategic pause)"| TT

    subgraph SOURCES ["Supported Sources"]
        S1["hackernews"]
        S2["youtube"]
        S3["github"]
        S4["google-linkedin"]
        S5["reddit"]
        S6["rss"]
        S7["google-news"]
        S8["podcasts"]
        S9["arxiv"]
    end

    FT --> SOURCES
```

Additionally, the **Validator node** uses internal URL-checking utilities (not agent tools):
- `extract_urls(text)` — regex extraction of HTTP/HTTPS URLs from text
- `validate_url(url)` — HEAD/GET reachability check
- `validate_urls(urls)` — batch validation returning `{url: bool}`

---

## 8. Module Map

```
src/lg_workflow_agent/
├── __init__.py          # Public API exports: WorkflowAgent, WorkflowGraphBuilder, WorkflowState
├── agent.py             # WorkflowAgent — top-level entry point (build, invoke, astream)
├── graph.py             # WorkflowGraphBuilder — LangGraph StateGraph construction
├── nodes.py             # Node factories (classifier, task_gen, aggregator, writer, validator, cleanup)
├── prompts.py           # All LLM prompt templates (classifier, task_gen, sub-agents, aggregator, writer, validator)
├── state.py             # WorkflowState TypedDict with reducer annotations
├── sub_agents.py        # Sub-agent construction (build_sub_agents) and runner factories (build_role_runners)
├── tools.py             # Tool re-exports (fetch_trends, think_tool) + URL validation utilities
└── run_sample.py        # Standalone sample script
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

The `WorkflowAgent` is a drop-in replacement for the simpler `ResearchAgent` (`src/agent/core.py`). Both expose the same `build()` / `invoke(query)` / `astream(query)` interface, but the workflow agent decomposes the query into parallel specialized sub-agents before producing the final report.

---

## 10. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Fan-out via `Send()`** | LangGraph's `Send` dispatches sub-agents in parallel; `worker_outputs` uses `Annotated[list, operator.add]` so results are appended, never overwritten |
| **Latest News Collection (not Content Drafting)** | The drafting role was running in parallel with research, producing prose without data. Replaced with a focused news-link collector; actual prose is written by the downstream **Writer** node which has access to all aggregated data |
| **Two-axis validation** | URL reachability alone isn't sufficient — an accessible but off-topic page is equally harmful. LLM relevance scoring catches fabricated or tangential references |
| **Max 2 rewrites** | Prevents infinite loops when the LLM keeps generating bad references. After 2 rewrites, invalid URLs are replaced with `[invalid link removed]` |
| **Sub-agents built once** | `create_agent` is called at graph-build time, not per-invocation. Runners are lightweight closures that just call `.invoke()` on the pre-built agent |
| **Best-effort persistence** | `_persist()` wraps all DB writes in try/except so a Qdrant outage never breaks the workflow |