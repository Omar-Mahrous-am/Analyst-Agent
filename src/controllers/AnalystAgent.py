import os
import sqlite3
import pandas as pd
from pathlib import Path
from typing import TypedDict, List, Annotated, Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from .BaseController import BaseController
from src.stores.llm.providers.AISuiteProvider import AISuiteProvider
from src.stores.llm.templates.locales.en.en_prompts import v1_prompt, reflect_v1_prompt,system_prompt
from tavily import TavilyClient

SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=SRC_DIR / ".env")


SCHEMA_PATH = SRC_DIR / "schema.txt"
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    db_schema = f.read()


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
    intent: str
    result:str


class AnalystAgent(BaseController):

    def __init__(self, model: str = None, tools: List = None, system: str = system_prompt.format(schema=db_schema)):
        self.system = system
        model = model or os.getenv("MODEL", "cohere:command-a-03-2025")
        classifiermodel=os.getenv("CLASSIFIER_MODEL")
        
        
        
        self.tools = {}
        
        self.client = AISuiteProvider(model_name=model)
        if self.tools:
            self.client.bind_tools(list(self.tools.values()))

        self.search_client=TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
        self.model_intent = AISuiteProvider(model_name=classifiermodel)

        
        graph = StateGraph(AgentState)

        graph.add_node("generate_sql_v1", self.generate_sql_v1)
        graph.add_node("execute_sql_v1", self.execute_sql_v1)
        graph.add_node("reflect_sql_v1", self.reflect_sql_v1)
        graph.add_node("execute_sql_v2", self.execute_sql_v2)
        graph.add_node("route_intent", self.intent_router_node)
        graph.add_node("search_web", self.search_web)

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
        graph.add_edge("reflect_sql_v1", "execute_sql_v2")
        graph.add_edge("execute_sql_v2", END)

        graph.add_edge("search_web",END)

        self.graph = graph.compile()


    class IntentRoute(BaseModel):
        intent: Literal["SQL Query", "General Q"] = Field(
            description="Select 'SQL Query' if the question requires database/SQL queries, otherwise select 'General Q'"
        )



    
    def intent_router_node(self, state: AgentState) -> dict:
        system_msg = "You are an intent classifier. Categorize whether the user query requires a database SQL query or a general web search."
        user_prompt = f"User Question: {state['question']}"

        
        response_text = self.model_intent.generate(prompt=user_prompt, system_instruction=system_msg)
        
        intent_val = "General Q"
        cleaned = response_text.strip().lower()
        if "sql" in cleaned or "database" in cleaned:
            intent_val = "SQL Query"

        return {"intent": intent_val}


    def decide_next_node(self,state: AgentState) -> str:
        if state["intent"] == "SQL Query":
            return "generate_sql_v1"
        return "search_web"




    
    
    def search_web(self,state: AgentState) -> dict:
        result = self.search_client.search(state["question"], max_results=2)

        result = result["results"][0]["content"]

        if not result:
            data="No Enough Information for User query"

        data=self.client.generate(prompt=f"User Question: {state['question']}\nWeb Search Result:\n{result}\nProvide a clear and concise answer to the user's question based on the web search results.",
                                                           system_instruction=self.system).strip()


        return {"messages": [AIMessage(content=data)],"result":data}
    

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

        prompt = v1_prompt.format(schema=schema,question=question)

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

        prompt = reflect_v1_prompt.format(question=question,schema=schema,sql_v1=sql_v1,df_v1=result_str)

        raw_v2 = self.client.generate(prompt=prompt, system_instruction=self.system).strip()
        sql_v2 = self._clean_sql(raw_v2)
        return {"sql_v2": sql_v2}

    def execute_sql_v2(self, state: AgentState) -> dict:
        sql_v2 = state["sql_v2"]
        db_path = state.get("db_path", "./db.sqlite")
        df_v2 = self.execute_sql(sql_v2, db_path)
        result_str = df_v2.to_string(index=False) if isinstance(df_v2, pd.DataFrame) else str(df_v2)
        return {"df_v2": df_v2,"result": result_str}