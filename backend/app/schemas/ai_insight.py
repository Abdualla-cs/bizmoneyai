from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class AIInsightOut(BaseModel):
    insight_id: int
    user_id: int
    title: str
    message: str
    severity: Literal["info", "warning", "critical"]
    period_start: date
    period_end: date
    created_at: datetime

    class Config:
        from_attributes = True
