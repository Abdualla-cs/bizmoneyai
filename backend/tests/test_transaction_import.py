from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.transactions import router as transactions_router
from app.core.security import create_access_token
from app.db.session import Base, get_db
from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User


@pytest.fixture()
def import_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    app = FastAPI()
    app.include_router(transactions_router)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    user = User(name="Importer", email="importer@example.com", password_hash="pw")
    db.add(user)
    db.commit()
    db.refresh(user)

    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    try:
        yield client, db, user
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_transaction_import_creates_categories_once_and_budgets_per_category(import_client):
    client, db, user = import_client

    response = client.post(
        "/transactions/import-file",
        files={
            "file": (
                "transactions.csv",
                "category_name,amount,type,description,date,budget_amount,budget_month\n"
                "Marketing,100,expense,Ads,2026-04-01,1000,2026-04\n"
                "marketing,50,expense,More ads,2026-04-02,1000,2026-04\n"
                "Rent,700,expense,Office rent,2026-04-03,750,2026-04\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 3
    assert body["skipped_count"] == 0
    assert body["rejected_rows"] == []

    categories = db.query(Category).filter(Category.user_id == user.user_id).order_by(Category.name.asc()).all()
    assert [(category.name, category.type) for category in categories] == [
        ("Marketing", "expense"),
        ("Rent", "expense"),
    ]

    budgets = db.query(Budget).filter(Budget.user_id == user.user_id).order_by(Budget.amount.asc()).all()
    assert len(budgets) == 2
    assert [(budget.amount, budget.month) for budget in budgets] == [
        (750.0, date(2026, 4, 1)),
        (1000.0, date(2026, 4, 1)),
    ]

    marketing = next(category for category in categories if category.name == "Marketing")
    marketing_transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.user_id, Transaction.category_id == marketing.category_id)
        .count()
    )
    assert marketing_transactions == 2


def test_transaction_import_skips_duplicate_rows_in_same_file(import_client):
    client, db, user = import_client

    response = client.post(
        "/transactions/import-file",
        files={
            "file": (
                "transactions.csv",
                "category_name,amount,type,description,date,budget_amount\n"
                "Meals,12.5,expense,Team lunch,2026-04-01,250\n"
                "meals,12.5,expense,Team lunch,2026-04-01,250\n"
                "Meals,15,expense,Client lunch,2026-04-02,250\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 2
    assert body["skipped_count"] == 1
    assert body["rejected_rows"] == [{"row_number": 3, "reason": "Duplicate row in import file"}]
    assert db.query(Transaction).filter(Transaction.user_id == user.user_id).count() == 2
    assert db.query(Category).filter(Category.user_id == user.user_id).count() == 1
    assert db.query(Budget).filter(Budget.user_id == user.user_id).count() == 1


def test_transaction_import_rejects_category_type_mismatch_without_partial_commit(import_client):
    client, db, user = import_client
    sales = Category(user_id=user.user_id, name="Sales", type="income")
    db.add(sales)
    db.commit()
    db.refresh(sales)

    response = client.post(
        "/transactions/import-file",
        files={
            "file": (
                "transactions.csv",
                "category_id,amount,type,description,date,budget_amount\n"
                f"{sales.category_id},40,expense,Invalid import,2026-04-01,100\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert "only supports income transactions" in response.json()["detail"]
    assert db.query(Transaction).filter(Transaction.user_id == user.user_id).count() == 0
    assert db.query(Budget).filter(Budget.user_id == user.user_id).count() == 0
