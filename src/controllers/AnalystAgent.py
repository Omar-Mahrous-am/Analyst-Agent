import os
import sqlite3
import pandas as pd
from pathlib import Path
from typing import TypedDict, List, Annotated
from dotenv import load_dotenv
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from langchain_core.messages import AIMessage
from .BaseController import BaseController
from src.stores.llm.providers.AISuiteProvider import AISuiteProvider
from src.stores.llm.templates.locales.en.en_prompts import system_prompt
from src.workflows import SQLReflectionWorkflow, WebSearchWorkflow, PythonCodeGenWorkflow
from tavily import TavilyClient
from langgraph.checkpoint.sqlite import SqliteSaver

# Load environment variables
SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=SRC_DIR / ".env")

# Load Database Schema
SCHEMA_PATH = SRC_DIR / "schema.txt"
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    db_schema = f.read()

# Setup assets directory for checkpoints
assets_dir = SRC_DIR / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)

# Define the State dictionary for the LangGraph workflow
# Note: Using dict instead of pd.DataFrame for df_v1 and df_v2 to ensure msgpack serialization compatibility with SqliteSaver
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    question: str
    schema: str
    model: str
    db_path: str
    sql_v1: str
    df_v1: dict
    sql_v2: str
    df_v2: dict
    intent: str
    result: str
    user_decision: str


class AnalystAgent(BaseController):
    def __init__(self, model: str = None, tools: List = None, system: str = system_prompt.format(schema=db_schema)):
        self.system = system
        model = model or os.getenv("MODEL", "cohere:command-a-03-2025")
        classifiermodel = os.getenv("CLASSIFIER_MODEL")
        
        self.tools = {}
        
        # Initialize LLM Providers
        self.client = AISuiteProvider(model_name=model)
        if self.tools:
            self.client.bind_tools(list(self.tools.values()))

        self.search_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
        self.model_intent = AISuiteProvider(model_name=classifiermodel)
        
        # Setup persistent checkpoint database
        checkpoint_db_path = str(assets_dir / "checkpoints.sqlite")
        self.conn = sqlite3.connect(checkpoint_db_path, check_same_thread=False)
        self.checkpointer = SqliteSaver(self.conn)
        self.checkpointer.setup()

        # Initialize Workflow Instances
        self.sql_workflow = SQLReflectionWorkflow(client=self.client, system_prompt=self.system)
        self.web_workflow = WebSearchWorkflow(client=self.client, search_client=self.search_client)
        self.python_workflow = PythonCodeGenWorkflow(client=self.client)

        # Initialize StateGraph
        graph = StateGraph(AgentState)

        # Define Graph Nodes
        graph.add_node("generate_sql_v1", self._generate_sql_v1)
        graph.add_node("execute_sql_v1", self._execute_sql_v1)
        graph.add_node("reflect_sql_v1", self._reflect_sql_v1)
        graph.add_node("execute_sql_v2", self._execute_sql_v2)
        graph.add_node("route_intent", self.intent_router_node)
        graph.add_node("search_web", self._search_web)
        graph.add_node("python_code_generator", self._python_code_generator)
        graph.add_node("human_approval_node", self.human_approval_node)

        # Define Graph Edges and Routing Logic
        graph.add_edge(START, "route_intent")
        graph.add_conditional_edges(
            "route_intent",
            self.decide_next_node,
            {
                "generate_sql_v1": "generate_sql_v1",
                "search_web": "search_web"
            }
        )
        graph.add_edge("generate_sql_v1", "execute_sql_v1")
        graph.add_edge("execute_sql_v1", "reflect_sql_v1")
        graph.add_edge("reflect_sql_v1", "human_approval_node")
        graph.add_conditional_edges(
            "human_approval_node",
            self.route_after_human,
            {
                "generate_sql_v1": "generate_sql_v1",         # Path 1: Reject & Rewrite
                "execute_sql_v2": "execute_sql_v2",           # Path 2: Direct SQL Execution
                "python_code_generator": "python_code_generator" # Path 3: Advanced Analysis & Viz
            }
        )

        graph.add_edge("execute_sql_v2", END)
        graph.add_edge("python_code_generator", END)
        graph.add_edge("search_web", END)

        # Compile the graph with the persistent checkpointer
        self.graph = graph.compile(checkpointer=self.checkpointer)

    # ===== INTENT CLASSIFIER & CONTROL LOGIC (Core - Stays in Controller) =====

    def intent_router_node(self, state: AgentState) -> dict:
        """Categorize whether the user query requires a DB SQL query or a general web search."""
        system_msg = "You are an intent classifier. Categorize whether the user query requires a database SQL query or a general web search."
        user_prompt = f"User Question: {state['question']}"

        response_text = self.model_intent.generate(prompt=user_prompt, system_instruction=system_msg)
        
        # Default to General Q unless database keywords are detected
        intent_val = "General Q"
        cleaned = response_text.strip().lower()
        if "sql" in cleaned or "database" in cleaned:
            intent_val = "SQL Query"

        return {"intent": intent_val}

    def decide_next_node(self, state: AgentState) -> str:
        """Route the workflow based on the classified intent."""
        if state["intent"] == "SQL Query":
            return "generate_sql_v1"
        return "search_web"

    def human_approval_node(self, state: AgentState) -> dict:
        """
        [HITL Interrupt Node]: Pauses the workflow, sends SQL V2 to the frontend, 
        and waits for human decision (Reject & Rewrite, Direct SQL Execution, or Advanced Analysis).
        """
        sql_v2 = state.get("sql_v2")
    
        # Interrupt pauses execution and sends this payload to the API/Frontend
        # The interrupt value becomes the "value" field in the client response
        interrupt({
            "action_required": "Please review the generated SQL",
            "sql_v2": sql_v2,
            "options": ["Reject & Rewrite", "Direct SQL Execution", "Advanced Analysis"]
            })
    
        # Execution pauses here until graph is resumed
        return {}

    def route_after_human(self, state: AgentState) -> str:
        """Routes execution based on human input received from the resume command."""
        # When graph is resumed, user_decision comes from the input passed to graph.invoke()
        decision = state.get("user_decision")
    
        if decision == "Reject & Rewrite":
            return "generate_sql_v1"
        elif decision == "Direct SQL Execution":
            return "execute_sql_v2"
        else:
            return "python_code_generator"

    # ===== WORKFLOW DELEGATORS (Thin Wrappers) =====

    def _generate_sql_v1(self, state: AgentState) -> dict:
        """Delegate to SQL workflow."""
        return self.sql_workflow.generate_sql_v1(state)

    def _execute_sql_v1(self, state: AgentState) -> dict:
        """Delegate to SQL workflow."""
        return self.sql_workflow.execute_sql_v1(state)

    def _reflect_sql_v1(self, state: AgentState) -> dict:
        """Delegate to SQL workflow."""
        return self.sql_workflow.reflect_sql_v1(state)

    def _execute_sql_v2(self, state: AgentState) -> dict:
        """Delegate to SQL workflow."""
        return self.sql_workflow.execute_sql_v2(state)

    def _search_web(self, state: AgentState) -> dict:
        """Delegate to Web Search workflow."""
        return self.web_workflow.search_web(state)

    def _python_code_generator(self, state: AgentState) -> dict:
        """Delegate to Python Code Gen workflow."""
        return self.python_workflow.python_code_generator(state)