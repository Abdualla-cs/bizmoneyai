from collections import defaultdict
from calendar import monthrange
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User


def normalize_month(value: date) -> date:
    return value.replace(day=1)


def month_bounds(month: date) -> tuple[date, date]:
    start = normalize_month(month)
    return start, date(start.year, start.month, monthrange(start.year, start.month)[1])


def budget_status(spent: float, amount: float) -> str:
    if spent > amount:
        return "over"
    if amount > 0 and spent >= amount * 0.8:
        return "near_limit"
    return "on_track"


def _spent_amounts_by_budget(db: Session, rows: list[tuple[Budget, str, str, str]]) -> dict[tuple[int, int, date], float]:
    if not rows:
        return {}

    months = [normalize_month(budget.month) for budget, *_ in rows]
    range_start = min(months)
    range_end = date(
        max(months).year,
        max(months).month,
        monthrange(max(months).year, max(months).month)[1],
    )
    user_ids = sorted({budget.user_id for budget, *_ in rows})
    category_ids = sorted({budget.category_id for budget, *_ in rows})

    spend_map: defaultdict[tuple[int, int, date], float] = defaultdict(float)
    spent_rows = (
        db.query(
            Transaction.user_id,
            Transaction.category_id,
            Transaction.date,
            Transaction.amount,
        )
        .filter(
            func.lower(Transaction.type) == "expense",
            Transaction.user_id.in_(user_ids),
            Transaction.category_id.in_(category_ids),
            Transaction.date >= range_start,
            Transaction.date <= range_end,
        )
        .all()
    )
    for tx_user_id, tx_category_id, tx_date, amount in spent_rows:
        spend_map[(tx_user_id, tx_category_id, normalize_month(tx_date))] += float(amount or 0.0)

    return dict(spend_map)


def list_budget_snapshots(db: Session, user_id: int | None = None, month: date | None = None) -> list[dict]:
    q = (
        db.query(Budget, Category.name, User.name, User.email)
        .join(Category, Category.category_id == Budget.category_id)
        .join(User, User.user_id == Budget.user_id)
        .filter(Category.user_id == Budget.user_id)
        .order_by(Budget.month.desc(), Category.name.asc())
    )
    if user_id is not None:
        q = q.filter(Budget.user_id == user_id, Category.user_id == user_id)
    if month is not None:
        q = q.filter(Budget.month == normalize_month(month))

    rows = q.all()
    spend_map = _spent_amounts_by_budget(db, rows)
    snapshots: list[dict] = []
    for budget, category_name, user_name, user_email in rows:
        budget_month = normalize_month(budget.month)
        total_spent = float(spend_map.get((budget.user_id, budget.category_id, budget_month), 0.0))
        snapshots.append(
            {
                "budget_id": budget.budget_id,
                "user_id": budget.user_id,
                "user_name": user_name,
                "user_email": user_email,
                "category_id": budget.category_id,
                "category_name": category_name,
                "amount": float(budget.amount),
                "spent": total_spent,
                "remaining": float(budget.amount - total_spent),
                "status": budget_status(total_spent, float(budget.amount)),
                "month": budget_month,
                "note": budget.note,
                "created_at": budget.created_at,
            }
        )
    return snapshots
