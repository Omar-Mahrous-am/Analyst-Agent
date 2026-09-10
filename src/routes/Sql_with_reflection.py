import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from src.schemas.sql import QueryRequest, QueryResponse
from src.controllers.AnalystAgent import AnalystAgent
from dotenv import load_dotenv
import pandas as pd

# Load environment variables from the parent src directory
SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=SRC_DIR / ".env")

sql_router = APIRouter(prefix="/api/v1/analyst", tags=["SQL Analyst"])

# Initialize tools list if needed
tools = [] 

@sql_router.post("/sql_gen", response_model=QueryResponse)
async def run_analyst_query(payload: QueryRequest):
    """
    Endpoint to process user queries through the AnalystAgent graph workflow,
    handling either database SQL generation/execution or general web searches.
    """
    try:
        model_name = os.getenv("MODEL", "cohere:command-a-03-2025")
        db_path = os.getenv("DB_PATH", "./db.sqlite")
        SCHEMA_PATH = SRC_DIR / "schema.txt"
        
        # Read the database schema definition file
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            db_schema = f.read()

        # 1. Instantiate the analyst agent with model and tools configuration
        agent = AnalystAgent(
            model=model_name, 
            tools=tools
        )

        # 2. Prepare the initial state dictionary for the LangGraph workflow
        initial_state = {
            "messages": [],
            "question": payload.question,
            "schema": db_schema,
            "model": model_name,
            "db_path": db_path,
        }

        # 3. Execute the compiled LangGraph workflow graph
        final_state = agent.graph.invoke(initial_state)

        # 4. Extract workflow intent and initialize container variables
        intent = final_state.get("intent")
        results_json = []
        web_search_content = None

        # 5. Handle responses dynamically based on the routing path taken (Web Search vs SQL)
        if intent == "General Q" or "web_search" in final_state or final_state.get("result"):
            # Extract content if the query was routed to the web search node
            web_search_content = final_state.get("result") or final_state.get("messages", [{}])[-1].content
        else:
            # Extract and serialize dataframe records if the query followed the SQL path
            df_final = final_state.get("df_v2")
            if isinstance(df_final, pd.DataFrame):
                results_json = df_final.where(pd.notnull(df_final), None).to_dict(orient="records")

        # Return the structured response matching the QueryResponse schema
        return QueryResponse(
            sql_v1=final_state.get("sql_v1", ""),
            sql_v2=final_state.get("sql_v2", ""),
            result=results_json,
            web_search=web_search_content
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing SQL request: {str(e)}"
        )