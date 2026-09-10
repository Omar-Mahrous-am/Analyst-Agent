from typing import Any, List, Dict
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., description="User question to be converted to SQL")


class QueryResponse(BaseModel):
    sql_v1: str
    sql_v2: str
    result: List[Dict[str, Any]]