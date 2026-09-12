import os
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.schemas.sql import QueryRequest
from src.controllers.AnalystAgent import AnalystAgent
from dotenv import load_dotenv

# Import Interrupt and Command from LangGraph
from langgraph.types import Interrupt, Command

# Resolve the root source directory and load environment variables
SRC_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=SRC_DIR / ".env")

# Initialize FastAPI router for the analyst endpoints
sql_router = APIRouter(prefix="/api/v1/analyst", tags=["SQL Analyst"])
tools = [] 

# 1. Define the custom JSON encoder to handle LangGraph Interrupt objects
def graph_encoder(obj):
    if isinstance(obj, Interrupt):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


@sql_router.post("/sql_gen")
async def run_analyst_query(payload: QueryRequest):
    """
    Endpoint to process user queries through the AnalystAgent graph workflow.
    Streams real-time node-based updates (SSE) for SQL execution steps and 
    token-based text streaming for general web searches.
    """
    try:
        model_name = os.getenv("MODEL", "cohere:command-a-03-2025")
        db_path = os.getenv("DB_PATH", "./db.sqlite")
        SCHEMA_PATH = SRC_DIR / "schema.txt"
        
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            db_schema = f.read()

        agent = AnalystAgent(model=model_name, tools=tools)

        initial_state = {
            "messages": [],
            "question": payload.question,
            "schema": db_schema,
            "model": model_name,
            "db_path": db_path,
        }

        # IMPORTANT: In production, thread_id should come from the request/user session
        thread = {"configurable": {"thread_id": "1"}}

        async def event_stream_generator():
            try:
                for event in agent.graph.stream(initial_state, config=thread, stream_mode="updates"):
                    for node_name, node_output in event.items():
                        
                        if node_name == "search_web":
                            web_content = node_output.get("result", "")
                            for word in web_content.split(" "):
                                yield f"data: {json.dumps({'node': node_name, 'token': word + ' '})}\n\n"
                        else:
                            # 2. Use the custom encoder here to safely serialize the Interrupt object
                            yield f"data: {json.dumps({'node': node_name, 'data': node_output}, default=graph_encoder)}\n\n"
                
                yield f"data: {json.dumps({'status': 'completed'})}\n\n"

            except Exception as stream_err:
                yield f"data: {json.dumps({'error': str(stream_err)})}\n\n"

        return StreamingResponse(event_stream_generator(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing SQL request: {str(e)}"
        )


# Schema for resuming the graph
class ResumeRequest(BaseModel):
    decision: str  # e.g., "Reject & Rewrite", "Direct SQL Execution", "Advanced Analysis"

@sql_router.post("/sql_resume")
async def resume_analyst_query(payload: ResumeRequest):
    """
    Endpoint to resume the paused graph with the human's decision.
    """
    try:
        model_name = os.getenv("MODEL", "cohere:command-a-03-2025")
        agent = AnalystAgent(model=model_name, tools=tools)

        # Must match the thread_id used in /sql_gen
        thread = {"configurable": {"thread_id": "1"}}

        async def resume_stream_generator():
            try:
                # 3. Use LangGraph Command to pass the decision back into the interrupt node
                resume_command = Command(resume=payload.decision)
                
                for event in agent.graph.stream(resume_command, config=thread, stream_mode="updates"):
                    for node_name, node_output in event.items():
                        yield f"data: {json.dumps({'node': node_name, 'data': node_output}, default=graph_encoder)}\n\n"
                
                yield f"data: {json.dumps({'status': 'completed'})}\n\n"

            except Exception as stream_err:
                yield f"data: {json.dumps({'error': str(stream_err)})}\n\n"

        return StreamingResponse(resume_stream_generator(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resuming SQL request: {str(e)}"
        )