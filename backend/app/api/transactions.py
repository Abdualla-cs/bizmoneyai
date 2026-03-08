import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _ensure_owned_category(db: Session, category_id: int, user_id: int) -> Category:
    category = (
        db.query(Category)
        .filter(Category.category_id == category_id, Category.user_id == user_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category for user")
    return category


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


@router.post("/import-csv", response_model=list[TransactionOut])
async def import_transactions_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in {"text/csv", "application/vnd.ms-excel"}:
        raise HTTPException(status_code=400, detail="Upload a CSV file")

    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    created: list[Transaction] = []

    for row in reader:
        category_id = int(row["category_id"])
        _ensure_owned_category(db, category_id, current_user.user_id)
        tx = Transaction(
            user_id=current_user.user_id,
            category_id=category_id,
            amount=float(row["amount"]),
            type=row["type"],
            description=row.get("description") or None,
            date=date.fromisoformat(row["date"]),
        )
        db.add(tx)
        created.append(tx)

    db.commit()
    for tx in created:
        db.refresh(tx)
    return created


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
