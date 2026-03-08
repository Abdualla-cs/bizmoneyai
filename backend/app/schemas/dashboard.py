from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_income: float
    total_expense: float
    balance: float
    transaction_count: int
