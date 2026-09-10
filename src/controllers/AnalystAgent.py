import os
import sqlite3
import pandas as pd
from pathlib import Path
from typing import TypedDict, List, Annotated
from dotenv import load_dotenv

from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages

from .BaseController import BaseController
from src.stores.llm.providers.AISuiteProvider import AISuiteProvider
from src.stores.llm.templates.locales.en.en_prompts import v1_prompt, reflect_v1_prompt

SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=SRC_DIR / ".env")


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    question: str
    schema: str
    model: str
    db_path: str
    sql_v1: str
    df_v1: pd.DataFrame
    sql_v2: str
    df_v2: pd.DataFrame


class AnalystAgent(BaseController):

    def __init__(self, model: str = None, tools: List = None, system: str = ""):
        self.system = system
        model = model or os.getenv("MODEL", "cohere:command-a-03-2025")
        
        tools = tools or []
        
        self.tools = {t.name: t for t in tools if hasattr(t, "name")}
        
        self.client = AISuiteProvider(model_name=model)
        if self.tools:
            self.client.bind_tools(list(self.tools.values()))

        
        graph = StateGraph(AgentState)

        graph.add_node("generate_sql_v1", self.generate_sql_v1)
        graph.add_node("execute_sql_v1", self.execute_sql_v1)
        graph.add_node("reflect_sql_v1", self.reflect_sql_v1)
        graph.add_node("execute_sql_v2", self.execute_sql_v2)

        graph.add_edge(START, "generate_sql_v1")
        graph.add_edge("generate_sql_v1", "execute_sql_v1")
        graph.add_edge("execute_sql_v1", "reflect_sql_v1")
        graph.add_edge("reflect_sql_v1", "execute_sql_v2")
        graph.add_edge("execute_sql_v2", END)

        self.graph = graph.compile()

    def _clean_sql(self, query: str) -> str:
        """Extract the SQL query from an LLM response.
        
        Handles:
        - JSON responses with a 'refined_sql' field
        - Markdown ```sql code blocks (possibly wrapped in prose)
        - Generic code fences
        """
        import re
        import json

        # Try to parse as JSON (or extract JSON from markdown code block)
        try:
            # Strip markdown json fences if present
            json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", query, re.DOTALL)
            json_str = json_match.group(1) if json_match else query
            data = json.loads(json_str)
            if isinstance(data, dict) and "refined_sql" in data:
                sql = data["refined_sql"]
                # The refined_sql value might itself contain ```sql fences
                inner = re.search(r"```sql\s*(.*?)\s*```", sql, re.DOTALL | re.IGNORECASE)
                return inner.group(1).strip() if inner else sql.strip()
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to extract SQL from a fenced code block
        match = re.search(r"```sql\s*(.*?)\s*```", query, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Fallback: strip any generic code fences
        match = re.search(r"```\s*(.*?)\s*```", query, re.DOTALL)
        if match:
            return match.group(1).strip()
        # No code block found — return stripped text as-is
        return query.strip()

    def execute_sql(self, query: str, db_path: str) -> pd.DataFrame:
        """Execute any SELECT over the SQLite database."""
        q = self._clean_sql(query)
        conn = sqlite3.connect(db_path)
        try:
            return pd.read_sql_query(q, conn)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})
        finally:
            conn.close()

    def generate_sql_v1(self, state: AgentState) -> dict:
        question = state["question"]
        schema = state["schema"]

        prompt = v1_prompt

        raw_v1 = self.client.generate(prompt=prompt, system_instruction=self.system).strip()
        sql_v1 = self._clean_sql(raw_v1)
        return {"sql_v1": sql_v1}

    def execute_sql_v1(self, state: AgentState) -> dict:
        sql_v1 = state["sql_v1"]
        db_path = state.get("db_path", "./db.sqlite")
        df_v1 = self.execute_sql(sql_v1, db_path)
        return {"df_v1": df_v1}

    def reflect_sql_v1(self, state: AgentState) -> dict:
        question = state["question"]
        schema = state["schema"]
        sql_v1 = state["sql_v1"]
        df_v1 = state["df_v1"]

        result_str = df_v1.to_string(index=False) if isinstance(df_v1, pd.DataFrame) else str(df_v1)

        prompt = reflect_v1_prompt

        raw_v2 = self.client.generate(prompt=prompt, system_instruction=self.system).strip()
        sql_v2 = self._clean_sql(raw_v2)
        return {"sql_v2": sql_v2}

    def execute_sql_v2(self, state: AgentState) -> dict:
        sql_v2 = state["sql_v2"]
        db_path = state.get("db_path", "./db.sqlite")
        df_v2 = self.execute_sql(sql_v2, db_path)
        return {"df_v2": df_v2}