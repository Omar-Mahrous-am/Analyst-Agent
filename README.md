# Analyst Agent

An intelligent AI-powered SQL analyst that leverages LLMs to understand natural language queries, generate optimized SQL, execute queries against databases, and fall back to web search for general questions. Built with FastAPI, LangGraph, and multi-model LLM support.

## 🎯 Overview

The **Analyst Agent** is a sophisticated agentic system that bridges the gap between natural language and SQL databases. It uses AI to:

- **Understand user intent** - Classifies whether a query requires database analysis or general knowledge
- **Generate SQL** - Creates SQL queries from natural language descriptions of data requirements
- **Execute safely** - Runs queries against SQLite databases with automatic reflection and validation
- **Improve iteratively** - Reflects on initial results and refines SQL if needed
- **Fall back intelligently** - Routes general questions to web search via Tavily API

## 🚀 Features

- **Multi-Model Support**: Works with OpenAI, Cohere, and other LLMs via AIStuite
- **LangGraph Workflow**: State-based graph architecture for complex agent orchestration
- **SQL Generation & Reflection**: Generate SQL from natural language, then reflect and refine results
- **Inventory Management Focus**: Pre-configured for product transaction analysis
- **Web Search Integration**: Seamless fallback to Tavily for non-database queries
- **FastAPI REST API**: Clean HTTP interface for query submission
- **Production-Ready**: Error handling, logging, and structured responses

## 📋 Requirements

### System Requirements
- Python 3.9+
- SQLite3

### Dependencies
See `src/requirements.txt` for complete list:

```
fastapi           # Web framework
sqlalchemy        # ORM and database toolkit
aisuite           # Multi-model LLM abstraction
langgraph         # Agent state graph framework
uvicorn           # ASGI server
pandas            # Data processing
openai            # OpenAI API (optional)
cohere            # Cohere API (optional)
python-dotenv     # Environment configuration
tavily            # Web search API
pydantic_settings # Settings management
```

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
   cp src/.env.example src/.env  # if available
   # Edit src/.env with your API keys
   ```

### Required Environment Variables

```bash
# LLM Configuration
MODEL=cohere:command-a-03-2025              # Default LLM model
CLASSIFIER_MODEL=cohere:command-a-03-2025   # Model for intent classification

# Database Configuration
DB_PATH=./src/assets/database/products.db   # Path to SQLite database

# API Keys (depending on which services you use)
OPENAI_API_KEY=sk-...                       # For OpenAI models
COHERE_API_KEY=...                          # For Cohere models
TAVILY_API_KEY=...                          # For web search functionality
```

## 📁 Project Structure

```
Analyst-Agent/
├── src/
│   ├── main.py                      # FastAPI application entry point
│   ├── requirements.txt             # Python dependencies
│   ├── schema.txt                   # Database schema definition
│   ├── .env                         # Environment variables (create from .env.example)
│   ├── .env.example                 # Example environment template
│   │
│   ├── controllers/
│   │   ├── BaseController.py        # Base class for controllers
│   │   └── AnalystAgent.py          # Main agent orchestration logic
│   │
│   ├── routes/
│   │   └── Sql_with_reflection.py   # FastAPI route handlers
│   │
│   ├── schemas/
│   │   └── sql.py                   # Pydantic request/response models
│   │
│   ├── stores/
│   │   └── llm/
│   │       ├── LLMInterface.py      # Base LLM interface
│   │       ├── LLMFactory.py        # LLM factory pattern
│   │       ├── providers/
│   │       │   └── AISuiteProvider.py  # AIStuite integration
│   │       └── templates/
│   │           └── locales/
│   │               └── en/
│   │                   └── en_prompts.py # English prompt templates
│   │
│   ├── helpers/
│   │   └── config.py                # Configuration utilities
│   │
│   ├── models/
│   │   └── db_schemas/              # SQLAlchemy models
│   │
│   └── assets/
│       ├── database/
│       │   └── products.db          # SQLite database with sample data
│       └── check_db.py              # Database inspection utility
│
├── LICENSE                           # MIT License
└── README.md                         # This file
```

## 🚀 Usage

### Starting the Server

```bash
cd src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

- **Interactive Docs**: `http://localhost:8000/docs`
- **Alternative Docs**: `http://localhost:8000/redoc`

### Making Queries

**Endpoint**: `POST /api/v1/analyst/sql_gen`

**Request Body**:
```json
{
  "question": "What were the top 5 best-selling products last month?"
}
```

**Response**:
```json
{
  "sql_v1": "SELECT product_name, SUM(qty_delta * -1) as total_qty FROM transactions WHERE action='sale' AND ts > datetime('now', '-1 month') GROUP BY product_name ORDER BY total_qty DESC LIMIT 5",
  "sql_v2": "SELECT product_name, SUM(-qty_delta * unit_price) as revenue FROM transactions WHERE action='sale' AND ts > datetime('now', '-1 month') GROUP BY product_name ORDER BY revenue DESC LIMIT 5",
  "result": [
    {"product_name": "Widget A", "revenue": 5000.00},
    {"product_name": "Widget B", "revenue": 4500.00},
    ...
  ],
  "web_search": null
}
```

### Database Schema

The agent is pre-configured for a `transactions` table tracking inventory events:

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| product_id | INTEGER | Foreign key to product |
| product_name | TEXT | Product display name |
| brand | TEXT | Brand name |
| category | TEXT | Product category |
| color | TEXT | Product color |
| action | TEXT | Event type: 'insert', 'sale', or 'restock' |
| qty_delta | INTEGER | Quantity change (negative for sales) |
| unit_price | REAL | Price per unit |
| notes | TEXT | Event description |
| ts | DATETIME | Event timestamp |

**Key Business Rules**:
- Total revenue = `SUM(-qty_delta * unit_price)` WHERE action = 'sale'
- Top-selling products ordered by revenue DESC (highest first)

## 🔄 How It Works

### Agent Workflow (LangGraph)

```
START
  ↓
[Classifier Node] → Determine intent (SQL vs General Q)
  ├─→ SQL Query Path
  │    ├→ [Generate SQL v1] → Create initial SQL
  │    ├→ [Execute Query] → Run against database
  │    └→ [Reflect v1] → Validate and refine if needed
  │
  └─→ General Q Path
       └→ [Web Search] → Search the internet
  ↓
END
```

1. **Intent Classification**: LLM determines if query requires database access or general knowledge
2. **SQL Generation**: Creates SQL from natural language and database schema
3. **Query Execution**: Safely executes SQL against SQLite database
4. **Reflection**: Reviews results and refines SQL if data looks incomplete
5. **Response Formatting**: Returns structured JSON with SQL statements and results

## 🛠️ Configuration

### Changing the LLM Model

Edit `src/.env`:
```bash
MODEL=openai:gpt-4                    # Use GPT-4
# or
MODEL=cohere:command-a-03-2025        # Use Cohere
```

### Using Different Database

Update `DB_PATH` in `src/.env`:
```bash
DB_PATH=/path/to/your/database.db
```

You'll also need to update `src/schema.txt` with your database schema.

## 📊 Database Inspection

To inspect the current database structure:

```bash
python src/assets/check_db.py
```

## 🔐 Security Considerations

- **SQL Injection**: The agent uses parameterized queries and SQLAlchemy ORM for safety
- **API Keys**: Keep API keys in `.env` file (never commit to version control)
- **Database Access**: Consider using read-only database users in production
- **Rate Limiting**: Consider adding rate limiting middleware for production deployments

## 🧪 Testing

The included `products.db` contains sample transaction data for testing:

```bash
cd src
python -c "
import sqlite3
conn = sqlite3.connect('assets/database/products.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM transactions LIMIT 5')
for row in cursor.fetchall():
    print(row)
"
```

## 📚 Prompt Architecture

The system uses multi-step prompts stored in `src/stores/llm/templates/locales/en/en_prompts.py`:

- **system_prompt**: Sets up the agent's role and context
- **v1_prompt**: Guides SQL generation from natural language
- **reflect_v1_prompt**: Asks the LLM to review and improve results

Prompts are automatically injected with the database schema for context-aware generation.

## 🚨 Error Handling

The API returns meaningful error messages:

```json
{
  "detail": "Error processing SQL request: [specific error message]"
}
```

HTTP Status Codes:
- `200`: Successful query execution
- `400`: Invalid request format
- `500`: Server error (LLM API issue, database error, etc.)

## 📝 Logging

Check application logs for debugging:

```bash
# Run with more verbose output
uvicorn main:app --log-level debug
```

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

- Support for additional database systems (PostgreSQL, MySQL, etc.)
- Multi-turn conversation support
- Query optimization suggestions
- Performance benchmarking
- Extended prompt templates for different domains

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright © 2026 Omar Mahrous

## 🙋 Support

For issues, questions, or suggestions:

1. Check existing GitHub issues
2. Review the prompt templates and schema for accuracy
3. Verify API keys and environment variables are correctly configured
4. Check database connectivity and schema alignment

## 🎓 Educational Notes

This project demonstrates:

- **LangGraph**: Building sophisticated agent workflows with state graphs
- **LLM Integration**: Working with multiple LLM providers through unified interfaces
- **SQL Generation**: Using LLMs for natural language to SQL translation
- **Agentic Patterns**: Implementing reflection, self-correction, and tool use
- **FastAPI**: Building production-ready REST APIs in Python
- **Factory Patterns**: Pluggable provider system for LLM selection

## 🔮 Future Enhancements

- [ ] Support for PostgreSQL, MySQL, and other databases
- [ ] Query optimization and performance analysis
- [ ] Conversation history and context awareness
- [ ] Query result caching
- [ ] Schema evolution handling
- [ ] Advanced error recovery strategies
- [ ] GraphQL API support
- [ ] Query cost estimation
- [ ] Database-specific SQL dialect support

---

**Version**: 1.0.0  
**Last Updated**: September 2026  
**Python**: 3.9+  
**Status**: Active Development