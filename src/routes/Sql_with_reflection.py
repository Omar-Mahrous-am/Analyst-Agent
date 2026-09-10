import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from src.schemas.sql import QueryRequest, QueryResponse
from src.controllers.AnalystAgent import AnalystAgent
from dotenv import load_dotenv
import pandas as pd

# Load .env from the src directory
SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=SRC_DIR / ".env")

sql_router = APIRouter(prefix="/api/v1/analyst", tags=["SQL Analyst"])

# Initialize tools if needed
tools = [] 

@sql_router.post("/sql_gen", response_model=QueryResponse)
async def run_analyst_query(payload: QueryRequest):
    try:
        model_name = os.getenv("MODEL", "cohere:command-a-03-2025")
        db_path = os.getenv("DB_PATH", "./db.sqlite")
        db_schema = os.getenv("DB_SCHEMA", "")

        # 1. Instantiate the agent
        agent = AnalystAgent(
            model=model_name, 
            tools=tools
        )

        # 2. Prepare the initial state
        initial_state = {
            "messages": [],
            "question": payload.question,
            "schema": db_schema,
            "model": model_name,
            "db_path": db_path,
        }

        # 3. Execute the LangGraph workflow
        final_state = agent.graph.invoke(initial_state)

        # 4. Extract DataFrame results to standard JSON serializable dicts
        df_final = final_state.get("df_v2")
        if isinstance(df_final, pd.DataFrame):
            results_json = df_final.where(pd.notnull(df_final), None).to_dict(orient="records")
        else:
            results_json = []

        return QueryResponse(
            sql_v1=final_state.get("sql_v1", ""),
            sql_v2=final_state.get("sql_v2", ""),
            result=results_json
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing SQL request: {str(e)}"
        )