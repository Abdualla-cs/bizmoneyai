from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminCreate(BaseModel):
    name: str
    email: EmailStr
    password_hash: str


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminOut(BaseModel):
    admin_id: int
    name: str
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
