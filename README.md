<div align="center">

# 🧠 Analyst Agent

### AI-Powered SQL Analyst with Agentic Reflection, Human-in-the-Loop Oversight, and Real-Time Streaming

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Stateful_Agents-1C3C3C?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Transform natural language questions into verified, production-safe SQL — with iterative self-correction, human approval gates, and live SSE streaming — all orchestrated by a LangGraph state machine.**

[Quick Start](#-quick-start) · [Architecture](#-architecture--system-design) · [API Reference](#-api-reference) · [Tech Stack](#-tech-stack)

</div>

---

## 📌 Why Analyst Agent?

Most LLM-to-SQL tools generate a query, execute it, and hope for the best. **Analyst Agent rejects that paradigm entirely.**

Instead, it implements a **multi-stage agentic pipeline** where every SQL query is generated, executed, introspected, reflected upon, and presented to a human for approval before final execution — all while streaming node-by-node state transitions to the client in real time via Server-Sent Events.

| Capability | Description |
|---|---|
| **Agentic SQL Reflection** | Generates SQL v1 → executes → inspects results/errors → self-corrects into SQL v2 |
| **Human-in-the-Loop (HITL)** | Pauses execution at a graph interrupt, presenting 3 decision paths to the user |
| **Stateful Checkpointing** | Persists full graph state to SQLite, enabling pause/resume across HTTP requests |
| **Real-Time SSE Streaming** | Streams every node transition, token-level web answers, and interrupt payloads live |
| **Multi-Provider LLM Support** | Pluggable architecture supporting OpenAI, Cohere, Anthropic via AISuite |
| **Intelligent Intent Routing** | Classifies queries as SQL-addressable or general knowledge, routing to the correct pipeline |
| **Web Search Fallback** | Tavily-powered deep search with LLM-synthesized answers for non-database queries |
| **Advanced Analytics Pipeline** | Routes approved data to Python code generation for statistical analysis and visualization |

---

## 🏗 Architecture & System Design

Analyst Agent is built on a **compiled LangGraph `StateGraph`** with 8 discrete nodes, 3 conditional routing edges, persistent SQLite checkpointing, and a human-in-the-loop interrupt gate. The graph supports cyclic re-entry (reject → regenerate loops) and 3-way branching after human review.

### High-Level Dataflow

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                           ANALYST AGENT — LangGraph State Machine                    │
│                                                                                      │
│  ┌─────────┐    ┌──────────────┐                                                     │
│  │  START   │───▶│ route_intent │                                                     │
│  └─────────┘    └──────┬───────┘                                                     │
│                        │                                                             │
│           ┌────────────┴────────────┐                                                │
│           │                         │                                                │
│      [SQL Query]              [General Q]                                            │
│           ▼                         ▼                                                │
│  ┌─────────────────┐     ┌───────────────────┐                                       │
│  │ generate_sql_v1 │     │    search_web      │                                       │
│  │ (LLM + Schema)  │     │ (Tavily + Synth)   │                                       │
│  └────────┬────────┘     └─────────┬─────────┘                                       │
│           ▼                        │                                                 │
│  ┌─────────────────┐               │                                                 │
│  │ execute_sql_v1  │               │                                                 │
│  │ (pandas + SQLite)│               │                                                 │
│  └────────┬────────┘               │                                                 │
│           ▼                        │                                                 │
│  ┌─────────────────┐               │                                                 │
│  │ reflect_sql_v1  │               │                                                 │
│  │ (Self-Correct)  │               │                                                 │
│  └────────┬────────┘               │                                                 │
│           ▼                        │                                                 │
│  ┌──────────────────────────┐      │                                                 │
│  │  human_approval_node     │      │                                                 │
│  │  ◀── INTERRUPT ──────── │      │                                                 │
│  │  State saved to SQLite   │      │                                                 │
│  └────────┬─────────────────┘      │                                                 │
│           │                        │                                                 │
│   ┌───────┼──────────┐             │                                                 │
│   │       │          │             │                                                 │
│   ▼       ▼          ▼             ▼                                                 │
│ ┌──────┐ ┌────────┐ ┌───────────┐                                                    │
│ │Reject│ │Execute │ │ Advanced  │                                                    │
│ │Rewrite│ │SQL v2  │ │ Analysis  │                                                    │
│ └──┬───┘ └───┬────┘ └─────┬─────┘                                                    │
│    │         │            │                                                          │
│    ▼         ▼            ▼                                                          │
│  ┌──────┐  ┌───┐   ┌──────────────────┐                                              │
│  │Loop  │  │END│   │python_code_gen   │                                              │
│  │Back  │  └───┘   │(pandas/matplotlib)│                                              │
│  └──────┘          └────────┬─────────┘                                              │
│    │                        │                                                        │
│    ▼                        ▼                                                        │
│ generate_sql_v1           ┌───┐                                                      │
│ (Cyclic Re-entry)         │END│                                                      │
│                           └───┘                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### Workflow Execution Stages

| Stage | Node | Description |
|---|---|---|
| 1 | `route_intent` | LLM-based intent classifier distinguishes SQL-addressable queries from general knowledge questions |
| 2 | `generate_sql_v1` | Injects database schema + user question into a few-shot prompt template; generates initial SQL |
| 3 | `execute_sql_v1` | Executes SQL v1 against SQLite via `pandas.read_sql_query()`; serializes results or errors to state |
| 4 | `reflect_sql_v1` | Analyzes v1 output against schema constraints and business rules; produces corrected SQL v2 |
| 5 | `human_approval_node` | **INTERRUPT** — Pauses graph, emits interrupt payload to client, persists state to `checkpoints.sqlite` |
| 6a | `execute_sql_v2` | Executes the human-approved SQL v2 and returns final results |
| 6b | `generate_sql_v1` | **Cyclic re-entry** — User rejected the query; regenerates from scratch |
| 6c | `python_code_generator` | Routes data to advanced analytics: statistical analysis, aggregations, and visualization code generation |
| 7 | `search_web` | Tavily deep search (3 results, advanced depth) → LLM-synthesized answer with token-level streaming |

---

## 📊 System Metrics & Specifications

| Metric | Value |
|---|---|
| **Graph Nodes** | 8 discrete processing nodes in a compiled `StateGraph` |
| **Graph Edges** | 10 edges (6 direct + 4 conditional routing edges) |
| **API Endpoints** | 3 RESTful endpoints (health check, query initiation, HITL resume) |
| **Streaming Protocol** | Server-Sent Events (SSE) with `text/event-stream` content type |
| **Workflow Pipelines** | 3 modular pipelines (SQL Reflection, Web Search, Python Code Gen) |
| **HITL Decision Paths** | 3 branches (Reject & Rewrite, Direct Execution, Advanced Analysis) |
| **State Properties** | 13 typed fields tracked across the `AgentState` TypedDict |
| **Prompt Templates** | 4 engineered prompt templates (system, v1 generation, reflection, advanced analysis) |
| **LLM Providers** | 3+ supported via AISuite (OpenAI, Cohere, Anthropic) |
| **SQL Sanitization Layers** | 3 extraction methods (JSON parsing, markdown fenced blocks, raw fallback) |
| **Web Search Depth** | Tavily `advanced` mode, top-3 results aggregated |
| **Checkpoint Persistence** | SQLite-backed `SqliteSaver` with WAL mode, supporting cross-request state resume |
| **LLM Temperature** | `0.0` (deterministic generation for SQL accuracy) |
| **Database Schema Columns** | 11 columns across 1 transaction table with 3 encoded business rules |

---

## 🔧 Tech Stack

### Generative AI & Agent Orchestration

| Technology | Purpose |
|---|---|
| [**LangGraph**](https://langchain-ai.github.io/langgraph/) | Compiles the multi-node `StateGraph` with conditional edges, cyclic re-entry, and `interrupt()` for HITL |
| [**AISuite**](https://github.com/andrewyng/aisuite) | Unified abstraction over OpenAI, Cohere, Anthropic — swap providers by changing a single env var |
| [**LangChain Core**](https://python.langchain.com/) | `AIMessage` primitives for message state management within the graph |
| [**Tavily**](https://tavily.com/) | Real-time deep web search API (advanced depth, 3 results per query) for non-SQL fallback |

### Backend & API Layer

| Technology | Purpose |
|---|---|
| [**FastAPI**](https://fastapi.tiangolo.com/) | Async-first web framework with automatic OpenAPI/Swagger docs, Pydantic validation, and SSE support |
| [**Uvicorn**](https://www.uvicorn.org/) | Lightning-fast ASGI server for production and hot-reload development |
| [**Pydantic**](https://docs.pydantic.dev/) | Request/response schema validation (`QueryRequest`, `QueryResponse`, `ResumeRequest`) |
| [**Pydantic Settings**](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | Type-safe environment configuration with `.env` file loading |

### Data Processing & Storage

| Technology | Purpose |
|---|---|
| [**SQLite**](https://www.sqlite.org/) | Embedded database for both application data and LangGraph checkpoint persistence |
| [**pandas**](https://pandas.pydata.org/) | SQL query execution (`read_sql_query`) and DataFrame serialization to state-compatible records |
| [**SQLAlchemy**](https://www.sqlalchemy.org/) | Database toolkit for ORM model definitions and schema management |

### Infrastructure & DevOps

| Technology | Purpose |
|---|---|
| [**python-dotenv**](https://github.com/theskumar/python-dotenv) | Secure environment variable management from `.env` files |
| [**langgraph-checkpoint-sqlite**](https://langchain-ai.github.io/langgraph/) | Persistent checkpoint storage enabling stateful graph pause/resume across HTTP requests |

---

## 🚀 Quick Start

### Prerequisites

- Python **3.9+**
- SQLite3 (included with Python)
- API keys for at least one LLM provider (Cohere, OpenAI, or Anthropic)
- Tavily API key (for web search functionality)

### 1. Clone & Setup

```bash
git clone https://github.com/Omar-Mahrous/Analyst-Agent.git
cd Analyst-Agent

# Create virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
```

### 2. Install Dependencies

```bash
pip install -r src/requirements.txt
```

### 3. Configure Environment

```bash
cp src/.env.example src/.env
```

Edit `src/.env` with your credentials:

```env
# ─── LLM Configuration ───────────────────────────────────────
MODEL=cohere:command-a-03-2025                 # Primary execution model
CLASSIFIER_MODEL=cohere:command-a-03-2025      # Intent classification model
APP_NAME=Analyst Agent

# ─── Database ────────────────────────────────────────────────
DB_PATH=./src/assets/database/products.db      # SQLite database path

# ─── API Keys (at least one LLM provider required) ──────────
COHERE_API_KEY=your_cohere_api_key
OPENAI_API_KEY=your_openai_api_key             # Optional
TAVILY_API_KEY=your_tavily_api_key             # Required for web search
```

> **Provider Swap**: To switch from Cohere to OpenAI, simply change `MODEL=openai:gpt-4o` — no code changes required.

### 4. Launch the Server

```bash
cd src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API is now live:

| Resource | URL |
|---|---|
| **API Root** | `http://localhost:8000/` |
| **Swagger UI** | `http://localhost:8000/docs` |
| **ReDoc** | `http://localhost:8000/redoc` |

---

## 📡 API Reference

### Endpoints Overview

| Method | Endpoint | Description | Response |
|---|---|---|---|
| `GET` | `/` | Health check and welcome message | JSON |
| `POST` | `/api/v1/analyst/sql_gen` | Initiate a new analyst workflow | SSE Stream |
| `POST` | `/api/v1/analyst/sql_resume` | Resume a paused HITL workflow | SSE Stream |

---

### `POST /api/v1/analyst/sql_gen`

Initiates the full analyst pipeline. Returns a **Server-Sent Events** stream with real-time node transitions.

**Request:**

```json
{
  "question": "What are our top 5 products by sales revenue?"
}
```

**SSE Response Stream:**

```text
data: {"node": "route_intent", "data": {"intent": "SQL Query"}}

data: {"node": "generate_sql_v1", "data": {"sql_v1": "SELECT product_name, SUM(-qty_delta * unit_price) AS revenue FROM transactions WHERE action = 'sale' GROUP BY product_name ORDER BY revenue DESC LIMIT 5;"}}

data: {"node": "execute_sql_v1", "data": {"df_v1": [{"product_name": "Pro Widget", "revenue": 14200.0}, {"product_name": "Alpha Sensor", "revenue": 11850.0}]}}

data: {"node": "reflect_sql_v1", "data": {"sql_v2": "SELECT product_name, SUM(-qty_delta * unit_price) AS total_revenue FROM transactions WHERE action = 'sale' GROUP BY product_name ORDER BY total_revenue DESC LIMIT 5;"}}

data: {"node": "interrupt_event", "data": {"action_required": "Please review the generated SQL", "sql_v2": "SELECT ...", "options": ["Reject & Rewrite", "Direct SQL Execution", "Advanced Analysis"]}}

data: {"status": "completed"}
```

#### Web Search Path

When the intent classifier routes to a general knowledge question, the response streams token-by-token:

```text
data: {"node": "route_intent", "data": {"intent": "General Q"}}
data: {"node": "search_web", "token": "The "}
data: {"node": "search_web", "token": "capital "}
data: {"node": "search_web", "token": "of "}
data: {"node": "search_web", "token": "France "}
data: {"node": "search_web", "token": "is "}
data: {"node": "search_web", "token": "Paris. "}
data: {"status": "completed"}
```

---

### `POST /api/v1/analyst/sql_resume`

Resumes a paused workflow after human review. Accepts one of 3 decision values.

**Request:**

```json
{
  "decision": "Direct SQL Execution"
}
```

**Decision Values:**

| Decision | Behavior |
|---|---|
| `"Direct SQL Execution"` | Executes the reflected SQL v2 query and returns results |
| `"Reject & Rewrite"` | Loops back to `generate_sql_v1` for a complete regeneration |
| `"Advanced Analysis"` | Routes data to the Python code generation pipeline |

**SSE Response (Direct Execution):**

```text
data: {"node": "execute_sql_v2", "data": {"df_v2": [{"product_name": "Pro Widget", "total_revenue": 14200.0}], "result": "[{...}]"}}

data: {"status": "completed"}
```

---

### Client Integration Example

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/v1/analyst"

# ─── Step 1: Initiate query and stream events ─────────────────
with requests.post(
    f"{BASE_URL}/sql_gen",
    json={"question": "What are our top 5 products by sales revenue?"},
    stream=True
) as response:
    for line in response.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data: "):
                event = json.loads(decoded[6:])
                print(f"[{event.get('node', 'status')}]", event)

                # Detect HITL interrupt
                if event.get("node") == "interrupt_event":
                    print("\n⚠️  Human review required!")
                    print(f"   SQL v2: {event['data']['sql_v2']}")
                    print(f"   Options: {event['data']['options']}")

# ─── Step 2: Resume with human decision ───────────────────────
with requests.post(
    f"{BASE_URL}/sql_resume",
    json={"decision": "Direct SQL Execution"},
    stream=True
) as response:
    for line in response.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data: "):
                event = json.loads(decoded[6:])
                print(f"[Resume] {event}")
```

**cURL Example:**

```bash
# Initiate a query
curl -N -X POST http://localhost:8000/api/v1/analyst/sql_gen \
  -H "Content-Type: application/json" \
  -d '{"question": "What are our top 5 products by sales revenue?"}'

# Resume with approval
curl -N -X POST http://localhost:8000/api/v1/analyst/sql_resume \
  -H "Content-Type: application/json" \
  -d '{"decision": "Direct SQL Execution"}'
```

---

## 📁 Project Structure

```
Analyst-Agent/
├── src/
│   ├── main.py                          # FastAPI application entrypoint
│   ├── requirements.txt                 # 12 Python dependencies
│   ├── schema.txt                       # Database schema + business rules (17 lines)
│   ├── .env / .env.example              # Environment configuration
│   │
│   ├── controllers/
│   │   ├── BaseController.py            # Abstract base with shared config & path utilities
│   │   └── AnalystAgent.py              # 8-node StateGraph orchestration, HITL interrupt, routing
│   │
│   ├── workflows/                       # Modular, decoupled pipeline implementations
│   │   ├── __init__.py                  # Public exports: 3 workflow classes
│   │   ├── sql_reflection_workflow.py   # SQL v1 gen → execute → reflect → v2 (4 methods, 117 lines)
│   │   ├── web_search_workflow.py       # Tavily search + LLM synthesis (45 lines)
│   │   └── python_code_gen_workflow.py  # Advanced analytics code generation (55 lines)
│   │
│   ├── routes/
│   │   └── Sql_with_reflection.py       # 2 SSE streaming endpoints + interrupt handling (120 lines)
│   │
│   ├── schemas/
│   │   ├── sql.py                       # QueryRequest, QueryResponse (Pydantic v2)
│   │   └── Intent_query_classify.py     # IntentClassification with confidence scoring
│   │
│   ├── stores/
│   │   └── llm/
│   │       ├── LLMInterface.py          # Abstract base class (generate method contract)
│   │       ├── LLMFactory.py            # Factory pattern for provider instantiation
│   │       ├── providers/
│   │       │   └── AISuiteProvider.py   # AISuite client: multi-provider, tool binding, temp=0.0
│   │       └── templates/
│   │           └── locales/en/
│   │               └── en_prompts.py    # 4 prompt templates (system, v1, reflect, advanced)
│   │
│   ├── helpers/
│   │   └── config.py                    # Pydantic Settings with .env loading
│   │
│   ├── models/
│   │   └── db_schemas/products/         # SQLAlchemy model definitions
│   │
│   └── assets/
│       ├── database/products.db         # Sample SQLite database (transactions table)
│       ├── checkpoints.sqlite           # LangGraph persistent state (WAL mode)
│       └── check_db.py                  # Database inspection utility
│
├── LICENSE                              # MIT License
└── README.md
```

---

## 🗃 Database Schema

The agent ships with a pre-configured `transactions` table modeling an inventory and sales system:

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | `PRIMARY KEY` | Auto-increment row identifier |
| `product_id` | `INTEGER` | `FK` | Foreign key to product catalog |
| `product_name` | `TEXT` | | Human-readable product display name |
| `brand` | `TEXT` | | Manufacturer brand name |
| `category` | `TEXT` | | Product category classification |
| `color` | `TEXT` | | Color variant descriptor |
| `action` | `TEXT` | | Event type: `'insert'` · `'sale'` · `'restock'` |
| `qty_delta` | `INTEGER` | | Inventory delta (negative for sales, positive for inserts/restocks) |
| `unit_price` | `REAL` | `NULLABLE` | Price per unit (`NULL` for restocks) |
| `notes` | `TEXT` | | Free-text transaction description |
| `ts` | `DATETIME` | | Event timestamp |

### Encoded Business Rules

These rules are injected into every LLM prompt to ensure SQL correctness:

```
Revenue Calculation:  SUM(-qty_delta * unit_price) WHERE action = 'sale'
Top-Selling Ranking:  ORDER BY total_revenue DESC
Quantity Negation:    qty_delta is negative for sales; negate to get positive values
```

---

## 🔐 Security Considerations

| Concern | Mitigation |
|---|---|
| **SQL Injection** | Generated queries are sanitized through 3-layer extraction (JSON → markdown fences → raw fallback) before execution |
| **Database Mutations** | SQLite connections should be configured in read-only mode for production deployments |
| **Secrets Management** | All API keys stored in `.env`, excluded from version control via `.gitignore` |
| **Multi-Tenant Isolation** | Thread-based session isolation via `{configurable: {thread_id: session_id}}` in checkpoint config |
| **LLM Prompt Injection** | Schema-constrained system prompts restrict the LLM to defined tables and columns only |

---

## 🧪 Verification

**Verify the database:**

```bash
cd src
python -c "
import sqlite3
conn = sqlite3.connect('assets/database/products.db')
cursor = conn.cursor()
cursor.execute('SELECT action, count(*) FROM transactions GROUP BY action')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]} records')
conn.close()
"
```

**Verify checkpoint persistence:**

```bash
python -c "
import sqlite3
conn = sqlite3.connect('src/assets/checkpoints.sqlite')
cursor = conn.cursor()
cursor.execute('SELECT count(*) FROM checkpoints')
print(f'Checkpoints recorded: {cursor.fetchone()[0]}')
conn.close()
"
```

**Run the database inspection utility:**

```bash
cd src/assets
python check_db.py
```

---

## 🗺 Roadmap

- [ ] **Multi-Dialect SQL Support** — PostgreSQL, MySQL, Snowflake, BigQuery adapters
- [ ] **Dynamic Session Management** — Per-user `thread_id` via FastAPI dependency injection
- [ ] **Advanced Visualization Pipeline** — Execute generated Python code and return charts as base64/images
- [ ] **Automated Test Suite** — Integration tests for each graph node with mocked LLM responses
- [ ] **Docker Compose Deployment** — Containerized setup with environment variable passthrough
- [ ] **Streaming WebSocket Support** — Upgrade from SSE to bidirectional WebSocket communication
- [ ] **Query History & Audit Log** — Persistent log of all queries, decisions, and results per session
- [ ] **Role-Based Access Control** — Restrict query execution permissions by user role

---

## 🤝 Contributing

Contributions are welcome. Please focus on the following high-impact areas:

1. **Multi-dialect SQL generators** — Extend `SQLReflectionWorkflow` for PostgreSQL, MySQL, or cloud warehouses
2. **Session management** — Implement per-user `thread_id` mapping via FastAPI middleware
3. **Python code execution** — Complete the `execution()`, `reflect_and_check_analysis()`, and `output_pdf()` methods in `PythonCodeGenWorkflow`
4. **Test coverage** — Unit tests for SQL sanitization, intent classification, and graph traversal
5. **Prompt engineering** — Improve few-shot examples and reflection prompt quality

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

Copyright © 2026 [Omar Mahrous](https://github.com/Omar-Mahrous)