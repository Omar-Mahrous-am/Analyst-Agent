from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str = Field(..., description="User question to be converted to SQL")


class QueryResponse(BaseModel):
    sql_v1: Optional[str] = ""
    sql_v2: Optional[str] = ""
    result: Optional[list] = []
    web_search: Optional[str] = None