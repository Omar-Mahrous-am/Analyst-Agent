# Analyst Agent

An intelligent, production-grade AI SQL analyst that leverages LLMs to understand natural language questions, generate and iteratively refine SQL queries, execute them safely against SQLite databases, and fall back to deep web search when appropriate. 

Built with **FastAPI**, **LangGraph**, **AISuite**, **Human-in-the-Loop (HITL)** approval workflows, **SQLite state checkpointing**, and real-time **Server-Sent Events (SSE)** streaming.

---

## 🎯 Overview

The **Analyst Agent** bridges the gap between non-technical users and relational databases. Rather than executing raw single-shot LLM queries, it incorporates agentic reflection, human oversight, and persistent state management:

- **Intent Classification** — Intelligently classifies whether a user's prompt requires database analysis or general knowledge.
- **Iterative SQL Generation & Reflection** — Generates initial SQL (v1), executes it against the database, inspects the result or error, and reflects to create an improved query (v2).
- **Human-in-the-Loop (HITL)** — Automatically pauses execution after SQL reflection, presenting the refined query to the user for approval, rewrite, or advanced data analysis routing.
- **State Checkpointing** — Preserves graph state across requests using `SqliteSaver`, allowing workflow pause and resume by session/thread ID.
- **Real-Time SSE Streaming** — Streams node-by-node updates, token-level web search answers, and interrupt events directly to the client over Server-Sent Events.
- **Deep Web Search Fallback** — Uses Tavily to fetch real-time web results and synthesize clear answers for non-database questions.

---

## 🚀 Features

- **Modular Workflow Architecture**: Decoupled workflow modules for SQL reflection, Tavily web search, and Python code generation under `src/workflows/`.
- **Human-in-the-Loop (HITL) Interruption**: Employs LangGraph `interrupt()` to pause execution and solicit human decisions (`Reject & Rewrite`, `Direct SQL Execution`, or `Advanced Analysis`).
- **Persistent State Checkpointing**: Built-in `SqliteSaver` checkpointer (`src/assets/checkpoints.sqlite`) enabling stateful conversations and seamless pause/resume capabilities.
- **Real-Time SSE Streaming**: Async streaming response endpoints (`/sql_gen` and `/sql_resume`) transmitting live node transitions, streaming tokens, and interrupt payloads.
- **Multi-Model Support via AISuite**: Pluggable provider architecture supporting OpenAI, Cohere, Anthropic, and other LLMs.
- **SQL Reflection & Self-Correction**: Automatically recovers from syntax errors or incomplete queries by analyzing execution results and refining the SQL.
- **Inventory & Transaction Domain Ready**: Pre-configured schema rules for product transactions, revenue calculations, and inventory tracking.
- **Web Search Integration**: Integrated Tavily deep search with LLM response synthesis for general queries.
- **FastAPI REST API**: High-performance, fully typed endpoints with automatic Swagger/OpenAPI documentation.

---

## 📋 Requirements

### System Requirements
- Python 3.9+
- SQLite3

### Key Dependencies
Listed in `src/requirements.txt`:

```
fastapi                      # Web framework
uvicorn                      # ASGI web server
langgraph                    # Agent orchestration and state graphs
langgraph-checkpoint-sqlite  # Persistent state checkpointing
aisuite                      # Unified multi-model LLM abstraction
sqlalchemy                   # Database toolkit and ORM
pandas                       # Data manipulation and query execution
tavily                       # Deep web search API
pydantic_settings            # Application configuration
python-dotenv                # Environment variable management
openai                       # OpenAI SDK (optional)
cohere                       # Cohere SDK (optional)
```

---

## 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Analyst-Agent
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r src/requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp src/.env.example src/.env
   ```
   Edit `src/.env` with your preferred model and API keys:

   ```bash
   # LLM Configuration
   MODEL=cohere:command-a-03-2025              # Execution LLM model
   CLASSIFIER_MODEL=cohere:command-a-03-2025   # Intent classification model

   # Database Configuration
   DB_PATH=./src/assets/database/products.db   # SQLite database path

   # API Keys
   COHERE_API_KEY=your_cohere_key_here
   OPENAI_API_KEY=your_openai_key_here        # Optional
   TAVILY_API_KEY=your_tavily_key_here        # Required for web search
   ```

---

## 📁 Project Structure

```
Analyst-Agent/
├── src/
│   ├── main.py                      # FastAPI app entrypoint
│   ├── requirements.txt             # Python dependencies
│   ├── schema.txt                   # Database schema definition
│   ├── .env                         # Environment configuration
│   ├── .env.example                 # Example environment template
│   │
│   ├── controllers/
│   │   ├── BaseController.py        # Base controller interface
│   │   └── AnalystAgent.py          # StateGraph orchestration & HITL routing
│   │
│   ├── workflows/                   # Modular workflow implementations
│   │   ├── __init__.py              # Workflow exports
│   │   ├── sql_reflection_workflow.py  # SQL v1, execution, reflection, and SQL v2
│   │   ├── web_search_workflow.py      # Tavily search & answer synthesis
│   │   └── python_code_gen_workflow.py # Python code generation & advanced analytics
│   │
│   ├── routes/
│   │   └── Sql_with_reflection.py   # FastAPI SSE streaming routes (/sql_gen, /sql_resume)
│   │
│   ├── schemas/
│   │   └── sql.py                   # Pydantic request/response schemas
│   │
│   ├── stores/
│   │   └── llm/
│   │       ├── LLMInterface.py      # LLM abstraction layer
│   │       ├── LLMFactory.py        # LLM provider factory
│   │       ├── providers/
│   │       │   └── AISuiteProvider.py  # AISuite client implementation
│   │       └── templates/
│   │           └── locales/en/
│   │               └── en_prompts.py   # System, SQL v1, and reflection prompts
│   │
│   ├── helpers/
│   │   └── config.py                # Environment and settings helpers
│   │
│   ├── models/
│   │   └── db_schemas/              # SQLAlchemy database models
│   │
│   └── assets/
│       ├── database/
│       │   └── products.db          # Sample SQLite database
│       ├── checkpoints.sqlite       # LangGraph persistent checkpoints
│       └── check_db.py              # Database inspection utility
│
├── LICENSE                          # MIT License
└── README.md                        # Documentation
```

---

## 🔄 How It Works

### LangGraph Agent Workflow

The agent uses a compiled LangGraph state machine with persistent SQLite checkpointing and human-in-the-loop interruption:

```
                     ┌─────────────────┐
                     │      START      │
                     └────────┬────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  route_intent   │
                     └────────┬────────┘
                              │
            ┌─────────────────┴─────────────────┐
     [SQL Query]                                [General Q]
            ▼                                   ▼
┌───────────────────────┐            ┌───────────────────────┐
│    generate_sql_v1    │            │      search_web       │
└───────────┬───────────┘            │   (Tavily + Synth)    │
            ▼                        └──────────┬────────────┘
┌───────────────────────┐                       │
│    execute_sql_v1     │                       │
└───────────┬───────────┘                       │
            ▼                                   │
┌───────────────────────┐                       │
│    reflect_sql_v1     │                       │
└───────────┬───────────┘                       │
            ▼                                   │
┌───────────────────────┐                       │
│  human_approval_node  │ ◄── [INTERRUPT]       │
└───────────┬───────────┘                       │
            │                                   │
   Human Decision Branch                        │
   ├── "Reject & Rewrite" ───────────┐          │
   │                                 │          │
   ├── "Direct SQL Execution"        │          │
   │        ▼                        │          │
   │   ┌─────────────────┐           │          │
   │   │ execute_sql_v2  │           │          │
   │   └────────┬────────┘           │          │
   │            │                    │          │
   └── "Advanced Analysis"           │          │
            ▼                        │          │
       ┌───────────────────────┐     │          │
       │ python_code_generator │     │          │
       └────────┬──────────────┘     │          │
                │                    │          │
                ▼                    ▼          ▼
             ┌─────┐              ┌───────────────┐
             │ END │              │generate_sql_v1│ (Loops back)
             └─────┘              └───────────────┘
```

### Workflow Execution Stages

1. **Intent Classification (`route_intent`)**:
   - Classifies user intent as either `SQL Query` or `General Q`.
2. **SQL Generation v1 (`generate_sql_v1`)**:
   - Injects the database schema and user question into the prompt template to generate an initial SQL query.
3. **Execution v1 (`execute_sql_v1`)**:
   - Runs SQL v1 against SQLite using pandas and formats records or errors into graph state.
4. **Reflection (`reflect_sql_v1`)**:
   - Analyzes the v1 results and schema rules to refine SQL into a corrected `sql_v2` query.
5. **Human-in-the-Loop Interrupt (`human_approval_node`)**:
   - Pauses graph execution with `interrupt()`, emitting an `interrupt_event` to the client with `sql_v2` and review options.
   - Graph state is saved to `checkpoints.sqlite`.
6. **Resume & Route**:
   - The user submits a decision via `/api/v1/analyst/sql_resume`:
     - **`Reject & Rewrite`**: Re-routes back to `generate_sql_v1` to regenerate a new query.
     - **`Direct SQL Execution`**: Advances to `execute_sql_v2` and executes the query against the database.
     - **`Advanced Analysis`**: Routes to `python_code_generator` for in-depth data processing and visualization.
7. **Web Search Path (`search_web`)**:
   - Queries Tavily for web context, streams synthesized response tokens, and completes.

---

## 🚀 API Usage & Endpoints

### 1. Start Server

```bash
cd src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive API Docs**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

---

### 2. Query Endpoint: `POST /api/v1/analyst/sql_gen`

Initiates the workflow and returns a real-time **Server-Sent Events (SSE)** stream.

**Request**:
```http
POST /api/v1/analyst/sql_gen
Content-Type: application/json

{
  "question": "What are our top 5 products by sales revenue?"
}
```

**SSE Event Stream (`text/event-stream`) Output**:

```text
data: {"node": "route_intent", "data": {"intent": "SQL Query"}}

data: {"node": "generate_sql_v1", "data": {"sql_v1": "SELECT product_name, SUM(-qty_delta * unit_price) AS revenue FROM transactions WHERE action = 'sale' GROUP BY product_name ORDER BY revenue DESC LIMIT 5;"}}

data: {"node": "execute_sql_v1", "data": {"df_v1": [{"product_name": "Pro Widget", "revenue": 14200.0}, ...]}}

data: {"node": "reflect_sql_v1", "data": {"sql_v2": "SELECT product_name, SUM(-qty_delta * unit_price) AS total_revenue FROM transactions WHERE action = 'sale' GROUP BY product_name ORDER BY total_revenue DESC LIMIT 5;"}}

data: {"node": "interrupt_event", "data": {"action_required": "Please review the generated SQL", "sql_v2": "SELECT product_name, SUM(-qty_delta * unit_price) AS total_revenue FROM transactions WHERE action = 'sale' GROUP BY product_name ORDER BY total_revenue DESC LIMIT 5;", "options": ["Reject & Rewrite", "Direct SQL Execution", "Advanced Analysis"]}}

data: {"status": "completed"}
```

> **Note**: When querying general knowledge (e.g., *"What is the capital of France?"*), the stream delivers token-by-token text from `search_web`:
> ```text
> data: {"node": "search_web", "token": "The "}
> data: {"node": "search_web", "token": "capital "}
> data: {"node": "search_web", "token": "of "}
> ...
> ```

---

### 3. Resume Endpoint: `POST /api/v1/analyst/sql_resume`

Resumes a paused workflow thread with the human's approval or steering decision.

**Request**:
```http
POST /api/v1/analyst/sql_resume
Content-Type: application/json

{
  "decision": "Direct SQL Execution"
}
```

*Valid decision values*:
- `"Direct SQL Execution"`: Executes `sql_v2` and outputs the result.
- `"Reject & Rewrite"`: Loops back to regenerate `sql_v1`.
- `"Advanced Analysis"`: Hands off data to the Python code generation workflow.

**SSE Event Stream Output (upon Direct SQL Execution)**:
```text
data: {"node": "execute_sql_v2", "data": {"df_v2": [{"product_name": "Pro Widget", "total_revenue": 14200.0}, ...], "result": "[{...}]"}}

data: {"status": "completed"}
```

---

### 4. Client Consumption Example (Python)

```python
import requests
import json

# 1. Start query and listen for events
url = "http://localhost:8000/api/v1/analyst/sql_gen"
payload = {"question": "What are our top 5 products by sales revenue?"}

with requests.post(url, json=payload, stream=True) as response:
    for line in response.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data: "):
                event = json.loads(decoded[6:])
                print(f"Received Event: {event}")
                
                # Check for Human-in-the-Loop Interrupt
                if event.get("node") == "interrupt_event":
                    print("\n[!] HITL Interrupt triggered. Options:", event["data"]["options"])

# 2. Resume with approval
resume_url = "http://localhost:8000/api/v1/analyst/sql_resume"
resume_payload = {"decision": "Direct SQL Execution"}

with requests.post(resume_url, json=resume_payload, stream=True) as response:
    for line in response.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data: "):
                event = json.loads(decoded[6:])
                print(f"Resume Event: {event}")
```

---

## 📊 Database Schema

The agent is pre-configured for a sample `transactions` table in `src/assets/database/products.db`:

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER | Primary key |
| `product_id` | INTEGER | Foreign key / product reference |
| `product_name` | TEXT | Display name of the product |
| `brand` | TEXT | Brand name |
| `category` | TEXT | Product category |
| `color` | TEXT | Color variant |
| `action` | TEXT | Transaction event: `'insert'`, `'sale'`, or `'restock'` |
| `qty_delta` | INTEGER | Delta in inventory (negative numbers for sales) |
| `unit_price` | REAL | Unit price of the item |
| `notes` | TEXT | Transaction notes / remarks |
| `ts` | DATETIME | Timestamp of the event |

**Business Rules Encoded in Prompt**:
- **Revenue Calculation**: `SUM(-qty_delta * unit_price) WHERE action = 'sale'`
- **Top-Selling Ranking**: Ordered by revenue or sold quantity in descending order (`DESC`).

To inspect database content directly:
```bash
python src/assets/check_db.py
```

---

## 🔐 Security & Production Best Practices

- **Read-Only Database Permissions**: Run the SQLite connection or production DB user in read-only mode to prevent unintended state mutations.
- **SQL Sanitization**: Generated queries are cleaned of markdown formatting and verified before execution.
- **Thread Isolation**: Map incoming user session IDs to `thread_id` in the checkpoint configuration (`{"configurable": {"thread_id": session_id}}`) for multi-tenant isolation.
- **Secrets Management**: Keep all API keys in `.env` and exclude sensitive files from git tracking.

---

## 🧪 Testing & Verification

Run a quick test against the SQLite database:

```bash
cd src
python -c "
import sqlite3
conn = sqlite3.connect('assets/database/products.db')
cursor = conn.cursor()
cursor.execute('SELECT action, count(*) FROM transactions GROUP BY action')
print(cursor.fetchall())
"
```

Verify LangGraph checkpoints:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('src/assets/checkpoints.sqlite')
cursor = conn.cursor()
cursor.execute('SELECT count(*) FROM checkpoints')
print('Checkpoints recorded:', cursor.fetchone()[0])
"
```

---

## 🤝 Contributing

Contributions are welcome! Suggested areas:
- Multi-dialect SQL generators (PostgreSQL, MySQL, Snowflake, BigQuery)
- Multi-tenant session thread management in FastAPI dependencies
- Enhanced visualization output for `PythonCodeGenWorkflow`
- Integration tests and automated regression test suite

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright © 2026 Omar Mahrous