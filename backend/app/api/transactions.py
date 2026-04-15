import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionImportResult, TransactionOut, TransactionUpdate
from app.services.admin_analytics import invalidate_admin_analytics_cache
from app.services.budget_metrics import normalize_month
from app.services.system_log import log_system_event

router = APIRouter(prefix="/transactions", tags=["transactions"])

CSV_CONTENT_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain", "application/octet-stream"}


def _ensure_owned_category(db: Session, category_id: int, user_id: int) -> Category:
    category = (
        db.query(Category)
        .filter(Category.category_id == category_id, Category.user_id == user_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category for user")
    return category


def _clean(value: object) -> str:
    return str(value or "").strip()


def _normalize_row(row: dict[str, str | None]) -> dict[str, str]:
    return {_clean(key).lower(): _clean(value) for key, value in row.items() if key is not None}


def _row_value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return ""


def _parse_positive_float(raw_value: str, *, row_number: int, field_name: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Row {row_number}: {field_name} must be a number") from exc
    if value <= 0:
        raise HTTPException(status_code=400, detail=f"Row {row_number}: {field_name} must be greater than 0")
    return value


def _parse_transaction_type(raw_value: str, *, row_number: int) -> str:
    value = raw_value.lower()
    if value not in {"income", "expense"}:
        raise HTTPException(status_code=400, detail=f"Row {row_number}: type must be income or expense")
    return value


def _parse_import_date(raw_value: str, *, row_number: int, field_name: str) -> date:
    value = raw_value
    if len(value) == 7 and value[4] == "-":
        value = f"{value}-01"
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Row {row_number}: {field_name} must be YYYY-MM-DD") from exc


def _category_supports_transaction(category: Category, transaction_type: str) -> bool:
    return category.type == transaction_type or category.type == "both"


def _ensure_category_supports_transaction(category: Category, transaction_type: str, row_number: int) -> None:
    if not _category_supports_transaction(category, transaction_type):
        raise HTTPException(
            status_code=400,
            detail=f"Row {row_number}: category '{category.name}' only supports {category.type} transactions",
        )


def _find_category_by_name(db: Session, *, user_id: int, name: str) -> Category | None:
    return (
        db.query(Category)
        .filter(Category.user_id == user_id, func.lower(Category.name) == name.lower())
        .first()
    )


def _get_or_create_import_category(
    db: Session,
    *,
    user_id: int,
    row: dict[str, str],
    transaction_type: str,
    row_number: int,
) -> Category:
    category_id_raw = _row_value(row, "category_id")
    category_name = _row_value(row, "category_name", "category")

    if category_id_raw:
        try:
            category_id = int(category_id_raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Row {row_number}: category_id must be a number") from exc
        category = _ensure_owned_category(db, category_id, user_id)
        _ensure_category_supports_transaction(category, transaction_type, row_number)
        return category

    if not category_name:
        raise HTTPException(status_code=400, detail=f"Row {row_number}: category_id or category_name is required")

    category = _find_category_by_name(db, user_id=user_id, name=category_name)
    if category:
        _ensure_category_supports_transaction(category, transaction_type, row_number)
        return category

    category = Category(user_id=user_id, name=category_name, type=transaction_type)
    db.add(category)
    db.flush()
    log_system_event(
        db,
        "create_category",
        f"Created category '{category.name}' from transaction import",
        user_id=user_id,
        entity_id=category.category_id,
        metadata={
            "category_name": category.name,
            "category_type": category.type,
            "source": "transaction_import",
        },
    )
    return category


def _existing_budget_for_month(db: Session, *, user_id: int, category_id: int, month: date) -> Budget | None:
    normalized_month = normalize_month(month)
    return (
        db.query(Budget)
        .filter(
            Budget.user_id == user_id,
            Budget.category_id == category_id,
            extract("year", Budget.month) == normalized_month.year,
            extract("month", Budget.month) == normalized_month.month,
        )
        .first()
    )


def _maybe_create_import_budget(
    db: Session,
    *,
    user_id: int,
    category: Category,
    row: dict[str, str],
    transaction_date: date,
    row_number: int,
    budget_requests: dict[tuple[int, date], float],
) -> None:
    budget_amount_raw = _row_value(row, "budget_amount", "budget")
    if not budget_amount_raw:
        return

    if category.type == "income":
        raise HTTPException(
            status_code=400,
            detail=f"Row {row_number}: budgets can only be imported for expense categories",
        )

    amount = _parse_positive_float(budget_amount_raw, row_number=row_number, field_name="budget_amount")
    budget_month_raw = _row_value(row, "budget_month", "month")
    budget_month = normalize_month(
        _parse_import_date(budget_month_raw, row_number=row_number, field_name="budget_month")
        if budget_month_raw
        else transaction_date
    )
    key = (category.category_id, budget_month)
    requested_amount = budget_requests.get(key)
    if requested_amount is not None:
        if requested_amount != amount:
            raise HTTPException(
                status_code=400,
                detail=f"Row {row_number}: conflicting budget_amount for category '{category.name}' in {budget_month.isoformat()}",
            )
        return

    budget_requests[key] = amount
    if _existing_budget_for_month(db, user_id=user_id, category_id=category.category_id, month=budget_month):
        return

    budget = Budget(user_id=user_id, category_id=category.category_id, amount=amount, month=budget_month)
    db.add(budget)
    db.flush()
    log_system_event(
        db,
        "create_budget",
        f"Created budget for category '{category.name}' from transaction import",
        user_id=user_id,
        entity_id=budget.budget_id,
        metadata={
            "category_id": category.category_id,
            "category_name": category.name,
            "amount": budget.amount,
            "month": budget.month.isoformat(),
            "source": "transaction_import",
        },
    )


async def _import_transactions_upload(
    *,
    file: UploadFile,
    db: Session,
    current_user: User,
) -> TransactionImportResult:
    file_name = file.filename or "transactions.csv"
    if file.content_type not in CSV_CONTENT_TYPES and not file_name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a CSV file")

    try:
        content = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Upload a UTF-8 CSV file") from exc

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV header row is required")

    created: list[Transaction] = []
    rejected_rows: list[dict[str, object]] = []
    seen_transactions: set[tuple[int, float, str, str, date]] = set()
    budget_requests: dict[tuple[int, date], float] = {}
    skipped_count = 0

    try:
        for row_number, raw_row in enumerate(reader, start=2):
            row = _normalize_row(raw_row)
            if not any(row.values()):
                continue

            amount_raw = _row_value(row, "amount")
            type_raw = _row_value(row, "type")
            date_raw = _row_value(row, "date")
            if not amount_raw:
                raise HTTPException(status_code=400, detail=f"Row {row_number}: amount is required")
            if not type_raw:
                raise HTTPException(status_code=400, detail=f"Row {row_number}: type is required")
            if not date_raw:
                raise HTTPException(status_code=400, detail=f"Row {row_number}: date is required")

            amount = _parse_positive_float(amount_raw, row_number=row_number, field_name="amount")
            transaction_type = _parse_transaction_type(type_raw, row_number=row_number)
            transaction_date = _parse_import_date(date_raw, row_number=row_number, field_name="date")
            description = _row_value(row, "description") or None
            category = _get_or_create_import_category(
                db,
                user_id=current_user.user_id,
                row=row,
                transaction_type=transaction_type,
                row_number=row_number,
            )

            duplicate_key = (category.category_id, amount, transaction_type, description or "", transaction_date)
            if duplicate_key in seen_transactions:
                skipped_count += 1
                rejected_rows.append({"row_number": row_number, "reason": "Duplicate row in import file"})
                continue
            seen_transactions.add(duplicate_key)

            _maybe_create_import_budget(
                db,
                user_id=current_user.user_id,
                category=category,
                row=row,
                transaction_date=transaction_date,
                row_number=row_number,
                budget_requests=budget_requests,
            )

            tx = Transaction(
                user_id=current_user.user_id,
                category_id=category.category_id,
                amount=amount,
                type=transaction_type,
                description=description,
                date=transaction_date,
            )
            db.add(tx)
            created.append(tx)

        log_system_event(
            db,
            "import_transactions",
            f"Imported {len(created)} transactions from {file_name}",
            user_id=current_user.user_id,
            metadata={
                "file_name": file_name,
                "imported_count": len(created),
                "skipped_count": skipped_count,
                "file_type": "csv",
            },
        )
        db.commit()
        invalidate_admin_analytics_cache()
    except HTTPException:
        db.rollback()
        raise

    for tx in created:
        db.refresh(tx)

    return TransactionImportResult(
        imported_count=len(created),
        skipped_count=skipped_count,
        rejected_rows=rejected_rows,
        transactions=created,
    )


@router.get("", response_model=list[TransactionOut])
def list_transactions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.user_id)
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        .all()
    )


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_owned_category(db, payload.category_id, current_user.user_id)
    tx = Transaction(user_id=current_user.user_id, **payload.model_dump())
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.get("/export-csv")
def export_transactions_csv(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    txs = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.user_id)
        .order_by(Transaction.date.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["transaction_id", "category_id", "amount", "type", "description", "date"])
    for tx in txs:
        writer.writerow([tx.transaction_id, tx.category_id, tx.amount, tx.type, tx.description or "", tx.date.isoformat()])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@router.post("/import-csv", response_model=TransactionImportResult)
async def import_transactions_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _import_transactions_upload(file=file, db=db, current_user=current_user)


@router.post("/import-file", response_model=TransactionImportResult)
async def import_transactions_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _import_transactions_upload(file=file, db=db, current_user=current_user)


@router.put("/{id}", response_model=TransactionOut)
def update_transaction(
    id: int,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tx = (
        db.query(Transaction)
        .filter(Transaction.transaction_id == id, Transaction.user_id == current_user.user_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        _ensure_owned_category(db, data["category_id"], current_user.user_id)

    for field, value in data.items():
        setattr(tx, field, value)

    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tx = (
        db.query(Transaction)
        .filter(Transaction.transaction_id == id, Transaction.user_id == current_user.user_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    db.delete(tx)
    db.commit()
    return None
