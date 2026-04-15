from datetime import date as dt_date, datetime
from typing import Literal

from pydantic import BaseModel


class TransactionCreate(BaseModel):
    category_id: int
    amount: float
    type: Literal["income", "expense"]
    description: str | None = None
    date: dt_date


class TransactionUpdate(BaseModel):
    category_id: int | None = None
    amount: float | None = None
    type: Literal["income", "expense"] | None = None
    description: str | None = None
    date: dt_date | None = None


class TransactionOut(BaseModel):
    transaction_id: int
    user_id: int
    category_id: int
    amount: float
    type: Literal["income", "expense"]
    description: str | None
    date: dt_date
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionImportRejectedRow(BaseModel):
    row_number: int
    reason: str


class TransactionImportResult(BaseModel):
    imported_count: int
    skipped_count: int
    rejected_rows: list[TransactionImportRejectedRow]
    transactions: list[TransactionOut]
