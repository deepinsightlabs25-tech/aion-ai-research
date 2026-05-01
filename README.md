# Aion AI Research Agent

A comprehensive, production-ready AI-powered research system that orchestrates a team of specialized sub-agents to generate, analyze, and synthesize detailed research reports. It consists of a FastAPI + LangGraph backend and a Vite + React frontend.

## 🌟 System Architecture & Workflow

The system uses a LangGraph-based workflow where specialized agents (Data Collection, Statistics, Citation, Web Research, Latest News) collaborate to draft the final research report.

```mermaid
graph TD
    User([User Request]) --> API[FastAPI Server]
    API --> Pipeline[Research Pipeline]
    
    subgraph LangGraph Workflow
        S[START] --> Classifier[Query Classifier Node]
        Classifier --> TaskGen[Task Generator Node]
        
        TaskGen -->|Fan-out| Agent1(Data Collection Agent)
        TaskGen -->|Fan-out| Agent2(Statistics Agent)
        TaskGen -->|Fan-out| Agent3(Citation Agent)
        TaskGen -->|Fan-out| Agent4(Web Research Agent)
        TaskGen -->|Fan-out| Agent5(Latest News Agent)
        
        Agent1 --> Agg[Aggregator Node]
        Agent2 --> Agg
        Agent3 --> Agg
        Agent4 --> Agg
        Agent5 --> Agg
        
        Agg --> Writer[Writer Node]
        Writer --> Validator{Validator Node}
        
        Validator -->|Rewrite| Writer
        Validator -->|Valid| Finalizer[Report Finalizer Node]
        
        Finalizer --> Cleanup[Cleanup Node]
        Cleanup --> E[END]
    end
    
    Pipeline -->|Init Graph| S
    Pipeline --> DB[(Qdrant / Postgres DB)]
    Pipeline -.->|Async Stream| UI[React Frontend]
```

## 🚀 Setup and Run the System

### Prerequisites
- Node.js (v18+)
- Python (v3.10+)
- `uv` (Fast Python package manager)
- Google GenAI API Key (for Gemini 2.5 Flash)

### 1. Backend Setup

The backend utilizes `uv` for dependency management and runs on FastAPI.

```bash
# Navigate to the backend directory
cd backend

# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync

# Configure environment variables
cp .env.example .env
# Open .env and add your GOOGLE_API_KEY and other credentials
```

**Run the Backend Server:**
```bash
# Starts the FastAPI server on http://localhost:8000
uv run run.py
```

### 2. Frontend Setup

The frontend is a Vite + React application.

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Configure environment variables
cp .env.example .env.local
# Make sure VITE_API_BASE_URL points to the backend (e.g., http://localhost:8000)

# Start the dev server
npm run dev
```
By default, the frontend will be available at `http://localhost:5175` or `http://localhost:3001` (based on your Vite port config).

---

## 🧩 Component Breakdown & Code Structure

### 1. The API Layer (Backend)
The FastAPI server (`backend/src/api/server.py`) handles HTTP requests. It uses background tasks to stream agent steps without blocking the thread pool.

**Backend Data Flow:**

```mermaid
sequenceDiagram
    participant C as Client (Frontend)
    participant API as FastAPI Router
    participant P as ResearchPipeline
    participant DB as Vector DB (Qdrant)
    participant LG as LangGraph Agent
    
    C->>API: POST /query { topic }
    API->>P: process_query(topic)
    P->>DB: Search Cache (cosine >= 0.85)
    
    alt Cache Hit
        DB-->>P: Existing Report
        P-->>API: { status: "found" }
        API-->>C: Returns cached report
    else Cache Miss
        P->>DB: Init Task Record
        P-->>API: { status: "processing", task_id }
        API-->>C: Returns task_id immediately
        
        Note over API,LG: Async Background Task
        API-)P: run_task_streaming(task_id)
        P->>LG: astream(initial_state)
        
        loop Every Graph Step
            LG-->>P: yield step_data
            P->>DB: Append step to task record
        end
        
        LG-->>P: yield final_report
        P->>DB: Store report in Cache
        P->>DB: Mark task "completed"
    end
```

```python
# backend/src/api/server.py
@app.post("/query", response_model=QueryResponse)
async def create_query(request: QueryRequest, user: dict = Depends(get_current_user)):
    # 1. Start processing the query
    result = pipeline.process_query(request.query)

    if result["status"] == "processing":
        # 2. Async stream is scheduled as a background task
        asyncio.create_task(
            pipeline.run_task_streaming(result["task_id"], request.query)
        )

    # 3. Immediately return the task_id to the client
    return QueryResponse(**result)
```

### 2. The LangGraph Agent Workflow (Backend)
The `WorkflowGraphBuilder` (`backend/src/lg_workflow_agent/graph.py`) defines the state machine of the research agent. It uses `StateGraph` to manage transitions between the classifier, task generator, sub-agents, writer, and validator nodes.

```python
# backend/src/lg_workflow_agent/graph.py
def build(self):
    wf = StateGraph(WorkflowState)

    wf.add_node("classifier", create_node_classifier(self.llm, self.db))
    wf.add_node("task_generator", create_node_task_generator(self.llm, self.db))
    # ... sub-agent nodes added here ...

    # Linear front: START -> classify -> task_gen -> fan-out
    wf.add_edge(START, "classifier")
    wf.add_edge("classifier", "task_generator")

    # Dynamic fan-out to specialized agents based on task breakdown
    wf.add_conditional_edges(
        "task_generator",
        create_assign_workers(),
        SUBAGENT_NODE_NAMES,
    )
    
    # ... aggregation and writing edges ...
    
    # Validation loop
    wf.add_conditional_edges(
        "validator",
        create_validation_route(),
        {"valid": "report_finalizer", "rewrite": "writer"},
    )
    
    return wf.compile()
```

### 3. The React Frontend (UI)
The frontend uses a state-machine-like approach in its main component (`frontend/src/pages/Home.jsx`) to cycle through Idle, Loading (Streaming), Result, or Error states. It streams the data by polling the streaming endpoint.

**Frontend Data Flow & State Management:**

```mermaid
sequenceDiagram
    participant U as User
    participant H as Home.jsx (State Orchestrator)
    participant A as api.js (Service)
    participant B as FastAPI Backend
    
    U->>H: Enters Topic & Submits
    H->>A: generateResearch(topic, onProgress)
    H->>H: State -> LOADING
    
    A->>B: POST /query { query: topic }
    B-->>A: { status: "processing", task_id: "123" }
    
    loop Every 1 second
        A->>B: GET /status?task_id=123
        B-->>A: { status: "processing", steps: [...] }
        A-->>H: onProgress(steps)
        H->>H: Render WorkflowGraphPanel & Loader
    end
    
    Note over A,B: Agent completes workflow
    B-->>A: { status: "completed", report: "..." }
    A-->>H: Return final report content
    H->>H: State -> RESULT
    H->>U: Render ResearchResult.jsx
```

**Key Frontend Modules & Components:**

- **`pages/Home.jsx` (State Orchestrator)**
  Manages the core `idle → loading → result/error` workflow. It ties the API polling loop with the view rendering.
  ```javascript
  // snippet from Home.jsx
  const handleSubmit = async (topic) => {
    setAppState(STATE.LOADING)
    try {
      const data = await runResearchQuery(topic, {
        onProgress: ({ status, steps }) => setProgressSteps(steps)
      })
      setResearch({ topic, content: data.content })
      setAppState(STATE.RESULT)
    } catch (err) {
      setAppState(STATE.ERROR)
    }
  }
  ```

- **`components/WorkflowGraphPanel.jsx` (Live Diagram)**
  A custom interactive SVG panel that visually tracks the LangGraph steps in real-time. It maps backend step logs (e.g., `classifier`, `writer`) to a dynamic LangGraph flowchart using CSS animations.

- **`components/ResearchResult.jsx` (Markdown Renderer)**
  Responsible for rendering the final generated markdown using `react-markdown`. It features custom URL transformations to render base64 embedded charts safely, and handles "Copy" and "Download .md" functionality.
  ```javascript
  // snippet from ResearchResult.jsx
  <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    urlTransform={(url) => /^data:image\/(png|jpe?g);/i.test(url) ? url : ''}
  >
    {content}
  </ReactMarkdown>
  ```

- **`components/TopicInput.jsx` & `components/Loader.jsx`**
  Handles user queries and visual feedback while polling the background task.

- **`services/api.js`**
  Manages communication with the FastAPI backend, initiating queries and polling `GET /status`.
  ```javascript
  // snippet from api.js
  while (true) {
      const statusRes = await axios.get(`${API_BASE}/status?task_id=${task_id}`);
      if (statusRes.data.status === 'completed') return statusRes.data.report;
      await new Promise(r => setTimeout(r, 1000)); // poll every 1s
  }
  ```

### 4. Database Integration
The system relies on a vector database (`Qdrant`) for caching previous research and storing semantic representations, paired with a relational/NoSQL layer (like `Postgres`) for task tracking and metadata tracking (`backend/src/db/`).

```python
# backend/src/db/postgres.py (Conceptual DB interaction)
def record_research_task(task_id, user_id, query, ...):
    # Store the initial task state in DB
    # Keeps track of which user initiated the workflow
    pass
```

## Summary
The combination of FastAPI (for async IO), LangGraph (for complex stateful multi-agent workflows), and React (for dynamic real-time visualization) forms a highly scalable AI application framework.
