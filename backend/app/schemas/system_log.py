from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SystemLogCreate(BaseModel):
    admin_id: int | None = None
    user_id: int | None = None
    event_type: str
    message: str
    level: str
    metadata: dict[str, Any] | None = None


class SystemLogOut(BaseModel):
    log_id: int
    admin_id: int | None
    user_id: int | None
    event_type: str
    message: str
    level: str
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_json")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
