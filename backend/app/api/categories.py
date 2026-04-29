from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.services.admin_analytics import invalidate_admin_analytics_cache
from app.services.system_log import log_system_event

router = APIRouter(prefix="/categories", tags=["categories"])


def _normalize_category_name(value: str) -> str:
    return " ".join(value.strip().split()).lower()


def _ensure_unique_category_name(
    db: Session,
    *,
    user_id: int,
    name: str,
    exclude_category_id: int | None = None,
) -> None:
    query = db.query(Category).filter(
        Category.user_id == user_id,
        func.lower(func.trim(Category.name)) == _normalize_category_name(name),
    )
    if exclude_category_id is not None:
        query = query.filter(Category.category_id != exclude_category_id)
    if query.first():
        raise HTTPException(status_code=400, detail="Category name already exists")


def _ensure_category_type_change_is_safe(
    db: Session,
    *,
    category: Category,
    new_type: str,
) -> None:
    if new_type == category.type or new_type == "both":
        return

    conflicting_transaction = (
        db.query(Transaction)
        .filter(
            Transaction.category_id == category.category_id,
            Transaction.type != new_type,
        )
        .first()
    )
    has_budgets = (
        db.query(Budget)
        .filter(Budget.category_id == category.category_id)
        .first()
        is not None
    )
    if conflicting_transaction or (new_type == "income" and has_budgets):
        raise HTTPException(
            status_code=400,
            detail=f"Category '{category.name}' cannot be changed to {new_type} while linked records require {category.type}",
        )


def _category_log_metadata(category: Category) -> dict[str, object]:
    return {
        "category_name": category.name,
        "category_type": category.type,
        "source": "category_api",
    }


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Category).filter(Category.user_id == current_user.user_id).order_by(Category.created_at.desc()).all()


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category_name = " ".join(payload.name.strip().split())
    _ensure_unique_category_name(db, user_id=current_user.user_id, name=category_name)

    category = Category(user_id=current_user.user_id, name=category_name, type=payload.type)
    db.add(category)
    db.flush()
    log_system_event(
        db,
        "create_category",
        f"Created category '{category.name}'",
        user_id=current_user.user_id,
        entity_id=category.category_id,
        metadata=_category_log_metadata(category),
    )
    db.commit()
    invalidate_admin_analytics_cache()
    db.refresh(category)
    return category


@router.put("/{id}", response_model=CategoryOut)
def update_category(
    id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category = (
        db.query(Category)
        .filter(Category.category_id == id, Category.user_id == current_user.user_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if payload.name is not None:
        category_name = " ".join(payload.name.strip().split())
        _ensure_unique_category_name(
            db,
            user_id=current_user.user_id,
            name=category_name,
            exclude_category_id=category.category_id,
        )
        category.name = category_name
    if payload.type is not None:
        _ensure_category_type_change_is_safe(db, category=category, new_type=payload.type)
        category.type = payload.type

    log_system_event(
        db,
        "update_category",
        f"Updated category '{category.name}'",
        user_id=current_user.user_id,
        entity_id=category.category_id,
        metadata=_category_log_metadata(category),
    )
    db.commit()
    invalidate_admin_analytics_cache()
    db.refresh(category)
    return category


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    category = (
        db.query(Category)
        .filter(Category.category_id == id, Category.user_id == current_user.user_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    linked_transactions = db.query(Transaction).filter(Transaction.category_id == category.category_id).count()
    linked_budgets = db.query(Budget).filter(Budget.category_id == category.category_id).count()
    if linked_transactions or linked_budgets:
        raise HTTPException(
            status_code=400,
            detail="Delete linked transactions and budgets before deleting this category",
        )

    metadata = _category_log_metadata(category)
    log_system_event(
        db,
        "delete_category",
        f"Deleted category '{category.name}'",
        user_id=current_user.user_id,
        entity_id=category.category_id,
        metadata=metadata,
    )
    db.delete(category)
    db.commit()
    invalidate_admin_analytics_cache()
    return None
