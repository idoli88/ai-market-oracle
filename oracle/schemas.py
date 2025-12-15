
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional

class AnalysisResponse(BaseModel):
    action: Literal["BUY", "SELL", "HOLD"] = Field(..., description="Action recommendation")
    emoji: str = Field(..., description="Emoji representing the action/sentiment")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    summary_he: str = Field(..., description="Short summary in Hebrew")
    key_points_he: List[str] = Field(..., max_length=5, description="List of up to 5 key technical points in Hebrew")
    invalidation_he: str = Field(..., description="Invalidation logic in Hebrew (or '-' if irrelevant)")
    risk_note_he: str = Field(..., description="Risk management note in Hebrew")

    @field_validator('key_points_he')
    def check_list_length(cls, v):
        if len(v) > 5:
            return v[:5]
        return v
