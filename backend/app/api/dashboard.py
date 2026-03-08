from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    income = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
        .filter(Transaction.user_id == current_user.user_id, Transaction.type == "income")
        .scalar()
    )
    expense = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
        .filter(Transaction.user_id == current_user.user_id, Transaction.type == "expense")
        .scalar()
    )
    count = db.query(func.count(Transaction.transaction_id)).filter(Transaction.user_id == current_user.user_id).scalar()

    return DashboardSummary(
        total_income=float(income or 0.0),
        total_expense=float(expense or 0.0),
        balance=float((income or 0.0) - (expense or 0.0)),
        transaction_count=int(count or 0),
    )
