from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    type: Literal["income", "expense", "both"]


class CategoryUpdate(BaseModel):
    name: str | None = None
    type: Literal["income", "expense", "both"] | None = None


class CategoryOut(BaseModel):
    category_id: int
    user_id: int
    name: str
    type: Literal["income", "expense", "both"]
    created_at: datetime

    class Config:
        from_attributes = True
