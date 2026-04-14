from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import and_, extract, func
from sqlalchemy.orm import Session

from app.models.ai_insight import AIInsight
from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.services.budget_metrics import budget_status, normalize_month

TimeGranularity = Literal["day", "month"]


@dataclass(frozen=True)
class TransactionQueryFilters:
    user_id: int
    date_from: date | None = None
    date_to: date | None = None
    transaction_type: Literal["income", "expense"] | None = None
    category_id: int | None = None


@dataclass(frozen=True)
class BudgetQueryFilters:
    user_id: int
    month: date | None = None
    month_from: date | None = None
    month_to: date | None = None
    category_id: int | None = None


@dataclass(frozen=True)
class InsightQueryFilters:
    user_id: int
    date_from: date | None = None
    date_to: date | None = None
    severity: Literal["info", "warning", "critical"] | None = None


@dataclass(frozen=True)
class TransactionTrainingRecord:
    transaction_id: int
    user_id: int
    category_id: int
    category_name: str
    category_type: str
    amount: float
    transaction_type: str
    description: str | None
    date: date
    created_at: datetime


@dataclass(frozen=True)
class BudgetTrainingRecord:
    budget_id: int
    user_id: int
    category_id: int
    category_name: str
    category_type: str
    amount: float
    spent: float
    remaining: float
    status: str
    month: date
    note: str | None
    created_at: datetime


@dataclass(frozen=True)
class InsightTrainingRecord:
    insight_id: int
    user_id: int
    title: str
    message: str
    severity: str
    period_start: date
    period_end: date
    created_at: datetime


@dataclass(frozen=True)
class TrainingDataBundle:
    transactions: list[TransactionTrainingRecord]
    budgets: list[BudgetTrainingRecord]
    insights: list[InsightTrainingRecord]


def _next_month_start(value: date) -> date:
    normalized = normalize_month(value)
    if normalized.month == 12:
        return normalized.replace(year=normalized.year + 1, month=1)
    return normalized.replace(month=normalized.month + 1)


def _next_day_start(value: date) -> datetime:
    return datetime.combine(value + timedelta(days=1), time.min)


def _apply_transaction_filters(query, filters: TransactionQueryFilters):
    query = query.filter(Transaction.user_id == filters.user_id)
    if filters.date_from is not None:
        query = query.filter(Transaction.date >= filters.date_from)
    if filters.date_to is not None:
        query = query.filter(Transaction.date <= filters.date_to)
    if filters.transaction_type is not None:
        query = query.filter(Transaction.type == filters.transaction_type)
    if filters.category_id is not None:
        query = query.filter(Transaction.category_id == filters.category_id)
    return query


def list_transactions_for_user(db: Session, filters: TransactionQueryFilters) -> list[Transaction]:
    query = _apply_transaction_filters(db.query(Transaction), filters)
    return query.order_by(Transaction.date.desc(), Transaction.created_at.desc()).all()


def _bucket_for_transaction_granularity(tx_date: date, granularity: TimeGranularity) -> date:
    if granularity == "month":
        return tx_date.replace(day=1)
    return tx_date


def query_transaction_timeseries(
    db: Session,
    filters: TransactionQueryFilters,
    *,
    granularity: TimeGranularity = "day",
) -> list[dict]:
    query = _apply_transaction_filters(
        db.query(
            Transaction.date,
            Transaction.type,
            func.count(Transaction.transaction_id).label("transactions_count"),
            func.coalesce(func.sum(Transaction.amount), 0.0).label("total_amount"),
        ),
        filters,
    )
    rows = (
        query
        .group_by(Transaction.date, Transaction.type)
        .order_by(Transaction.date.asc(), Transaction.type.asc())
        .all()
    )

    buckets: dict[date, dict[str, int | float | date]] = {}
    for tx_date, transaction_type, count, total_amount in rows:
        bucket = _bucket_for_transaction_granularity(tx_date, granularity)
        entry = buckets.setdefault(
            bucket,
            {
                "bucket": bucket,
                "transactions_count": 0,
                "income_total": 0.0,
                "expense_total": 0.0,
                "net_total": 0.0,
            },
        )
        entry["transactions_count"] = int(entry["transactions_count"]) + int(count or 0)
        amount = float(total_amount or 0.0)
        if transaction_type == "income":
            entry["income_total"] = float(entry["income_total"]) + amount
            entry["net_total"] = float(entry["net_total"]) + amount
        else:
            entry["expense_total"] = float(entry["expense_total"]) + amount
            entry["net_total"] = float(entry["net_total"]) - amount

    return [buckets[key] for key in sorted(buckets.keys())]


def _apply_budget_filters(query, filters: BudgetQueryFilters):
    query = query.filter(Budget.user_id == filters.user_id, Category.user_id == Budget.user_id)
    if filters.month is not None:
        query = query.filter(Budget.month == normalize_month(filters.month))
    else:
        if filters.month_from is not None:
            query = query.filter(Budget.month >= normalize_month(filters.month_from))
        if filters.month_to is not None:
            query = query.filter(Budget.month <= normalize_month(filters.month_to))
    if filters.category_id is not None:
        query = query.filter(Budget.category_id == filters.category_id)
    return query


def _budget_rows_with_spend(db: Session, filters: BudgetQueryFilters):
    spend_query = (
        db.query(
            Transaction.user_id.label("user_id"),
            Transaction.category_id.label("category_id"),
            extract("year", Transaction.date).label("tx_year"),
            extract("month", Transaction.date).label("tx_month"),
            func.coalesce(func.sum(Transaction.amount), 0.0).label("spent"),
        )
        .filter(Transaction.type == "expense", Transaction.user_id == filters.user_id)
    )

    if filters.month is not None:
        normalized_month = normalize_month(filters.month)
        spend_query = spend_query.filter(
            extract("year", Transaction.date) == normalized_month.year,
            extract("month", Transaction.date) == normalized_month.month,
        )
    else:
        if filters.month_from is not None:
            spend_query = spend_query.filter(Transaction.date >= normalize_month(filters.month_from))
        if filters.month_to is not None:
            spend_query = spend_query.filter(Transaction.date < _next_month_start(filters.month_to))
        if filters.category_id is not None:
            spend_query = spend_query.filter(Transaction.category_id == filters.category_id)

    spend_subquery = (
        spend_query
        .group_by(
            Transaction.user_id,
            Transaction.category_id,
            extract("year", Transaction.date),
            extract("month", Transaction.date),
        )
        .subquery()
    )

    query = (
        db.query(
            Budget,
            Category.name.label("category_name"),
            Category.type.label("category_type"),
            User.name.label("user_name"),
            User.email.label("user_email"),
            func.coalesce(spend_subquery.c.spent, 0.0).label("spent"),
        )
        .join(Category, Category.category_id == Budget.category_id)
        .join(User, User.user_id == Budget.user_id)
        .outerjoin(
            spend_subquery,
            and_(
                spend_subquery.c.user_id == Budget.user_id,
                spend_subquery.c.category_id == Budget.category_id,
                spend_subquery.c.tx_year == extract("year", Budget.month),
                spend_subquery.c.tx_month == extract("month", Budget.month),
            ),
        )
    )
    return _apply_budget_filters(query, filters)


def _serialize_budget_rows(rows) -> tuple[list[dict], list[BudgetTrainingRecord]]:
    snapshots: list[dict] = []
    training_records: list[BudgetTrainingRecord] = []
    for budget, category_name, category_type, user_name, user_email, spent in rows:
        budget_month = normalize_month(budget.month)
        total_spent = float(spent or 0.0)
        remaining = float(budget.amount - total_spent)
        status = budget_status(total_spent, float(budget.amount))
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
                "remaining": remaining,
                "status": status,
                "month": budget_month,
                "note": budget.note,
                "created_at": budget.created_at,
            }
        )
        training_records.append(
            BudgetTrainingRecord(
                budget_id=budget.budget_id,
                user_id=budget.user_id,
                category_id=budget.category_id,
                category_name=category_name,
                category_type=category_type,
                amount=float(budget.amount),
                spent=total_spent,
                remaining=remaining,
                status=status,
                month=budget_month,
                note=budget.note,
                created_at=budget.created_at,
            )
        )
    return snapshots, training_records


def list_budget_snapshots_for_user(db: Session, filters: BudgetQueryFilters) -> list[dict]:
    rows = _budget_rows_with_spend(db, filters).order_by(Budget.month.desc(), Category.name.asc()).all()
    snapshots, _training_records = _serialize_budget_rows(rows)
    return snapshots


def query_budget_timeseries(
    db: Session,
    filters: BudgetQueryFilters,
    *,
    granularity: Literal["month"] = "month",
) -> list[dict]:
    del granularity
    rows = _budget_rows_with_spend(db, filters).order_by(Budget.month.asc(), Category.name.asc()).all()
    buckets: dict[date, dict[str, int | float | date]] = {}
    for budget, _category_name, _category_type, _user_name, _user_email, spent in rows:
        bucket = normalize_month(budget.month)
        entry = buckets.setdefault(
            bucket,
            {
                "bucket": bucket,
                "budgets_count": 0,
                "total_budgeted": 0.0,
                "total_spent": 0.0,
                "over_budget_count": 0,
            },
        )
        budget_amount = float(budget.amount)
        total_spent = float(spent or 0.0)
        entry["budgets_count"] = int(entry["budgets_count"]) + 1
        entry["total_budgeted"] = float(entry["total_budgeted"]) + budget_amount
        entry["total_spent"] = float(entry["total_spent"]) + total_spent
        if budget_status(total_spent, budget_amount) == "over":
            entry["over_budget_count"] = int(entry["over_budget_count"]) + 1

    return [buckets[key] for key in sorted(buckets.keys())]


def _apply_insight_filters(query, filters: InsightQueryFilters):
    query = query.filter(AIInsight.user_id == filters.user_id)
    if filters.date_from is not None:
        query = query.filter(AIInsight.created_at >= datetime.combine(filters.date_from, datetime.min.time()))
    if filters.date_to is not None:
        query = query.filter(AIInsight.created_at < _next_day_start(filters.date_to))
    if filters.severity is not None:
        query = query.filter(AIInsight.severity == filters.severity)
    return query


def list_insights_for_user(db: Session, filters: InsightQueryFilters) -> list[AIInsight]:
    query = _apply_insight_filters(db.query(AIInsight), filters)
    return query.order_by(AIInsight.created_at.desc()).all()


def _bucket_for_created_at(created_at: datetime, granularity: TimeGranularity) -> date:
    if granularity == "month":
        return created_at.date().replace(day=1)
    return created_at.date()


def query_insight_timeseries(
    db: Session,
    filters: InsightQueryFilters,
    *,
    granularity: TimeGranularity = "day",
) -> list[dict]:
    query = _apply_insight_filters(
        db.query(
            func.date(AIInsight.created_at).label("bucket_day"),
            AIInsight.severity,
            func.count(AIInsight.insight_id).label("insights_count"),
        ),
        filters,
    )
    rows = (
        query
        .group_by(func.date(AIInsight.created_at), AIInsight.severity)
        .order_by(func.date(AIInsight.created_at).asc(), AIInsight.severity.asc())
        .all()
    )

    buckets: dict[date, dict[str, int | date]] = {}
    for bucket_day, severity, insights_count in rows:
        created_at = datetime.combine(date.fromisoformat(str(bucket_day)), time.min)
        bucket = _bucket_for_created_at(created_at, granularity)
        entry = buckets.setdefault(
            bucket,
            {
                "bucket": bucket,
                "insights_count": 0,
                "info_count": 0,
                "warning_count": 0,
                "critical_count": 0,
            },
        )
        count = int(insights_count or 0)
        entry["insights_count"] = int(entry["insights_count"]) + count
        key = f"{severity}_count"
        entry[key] = int(entry[key]) + count

    return [buckets[key] for key in sorted(buckets.keys())]


def extract_training_data_bundle(
    db: Session,
    *,
    user_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
) -> TrainingDataBundle:
    normalized_month_from = date_from.replace(day=1) if date_from is not None else None
    normalized_month_to = date_to.replace(day=1) if date_to is not None else None

    transaction_rows = (
        _apply_transaction_filters(
            db.query(
                Transaction.transaction_id,
                Transaction.user_id,
                Transaction.category_id,
                Category.name,
                Category.type,
                Transaction.amount,
                Transaction.type,
                Transaction.description,
                Transaction.date,
                Transaction.created_at,
            ).join(Category, Category.category_id == Transaction.category_id),
            TransactionQueryFilters(user_id=user_id, date_from=date_from, date_to=date_to),
        )
        .order_by(Transaction.date.asc(), Transaction.transaction_id.asc())
        .all()
    )
    transactions = [
        TransactionTrainingRecord(
            transaction_id=transaction_id,
            user_id=tx_user_id,
            category_id=category_id,
            category_name=category_name,
            category_type=category_type,
            amount=float(amount),
            transaction_type=transaction_type,
            description=description,
            date=tx_date,
            created_at=created_at,
        )
        for transaction_id, tx_user_id, category_id, category_name, category_type, amount, transaction_type, description, tx_date, created_at in transaction_rows
    ]

    budget_rows = _budget_rows_with_spend(
        db,
        BudgetQueryFilters(
            user_id=user_id,
            month_from=normalized_month_from,
            month_to=normalized_month_to,
        ),
    ).order_by(Budget.month.asc(), Category.name.asc()).all()
    _snapshots, budgets = _serialize_budget_rows(budget_rows)

    insights = [
        InsightTrainingRecord(
            insight_id=insight.insight_id,
            user_id=insight.user_id,
            title=insight.title,
            message=insight.message,
            severity=insight.severity,
            period_start=insight.period_start,
            period_end=insight.period_end,
            created_at=insight.created_at,
        )
        for insight in list_insights_for_user(
            db,
            InsightQueryFilters(user_id=user_id, date_from=date_from, date_to=date_to),
        )
    ]

    return TrainingDataBundle(
        transactions=transactions,
        budgets=budgets,
        insights=insights,
    )
