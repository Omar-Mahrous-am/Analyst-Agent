from pydantic import BaseModel, Field
from typing import Literal



class IntentClassification(BaseModel):
    intent: Literal["SQL Query", "General Q"]=Field(..., description="Classify whether the user query requires a database SQL query or a general web search.")
    confidence: float = Field(..., description="Confidence score between 0 and 1",ge=0.0, le=1.0)