from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.admin import router as admin_router
from app.core.security import create_admin_access_token
from app.db.session import Base, get_db
from app.models.admin import Admin
from app.models.ai_insight import AIInsight
from app.models.budget import Budget
from app.models.category import Category
from app.models.system_log import SystemLog
from app.models.transaction import Transaction
from app.models.user import User


@pytest.fixture()
def admin_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    app = FastAPI()
    app.include_router(admin_router)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    admin = Admin(name="Ops Admin", email="admin@example.com", password_hash="secret123")
    db.add(admin)
    db.commit()
    db.refresh(admin)

    client = TestClient(app)
    client.cookies.set("admin_access_token", create_admin_access_token(str(admin.admin_id)))

    try:
        yield client, db
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def _seed_users(db):
    base_time = datetime(2026, 4, 15, 9, 0, 0)
    users = [
        User(name="Charlie Founder", email="charlie@example.com", password_hash="pw", created_at=base_time + timedelta(minutes=2)),
        User(name="Alice Owner", email="alice@example.com", password_hash="pw", created_at=base_time),
        User(name="Bob Builder", email="bob@example.com", password_hash="pw", created_at=base_time + timedelta(minutes=1)),
    ]
    db.add_all(users)
    db.commit()
    for user in users:
        db.refresh(user)
    return users


def _seed_user_context_data(db):
    base_time = datetime(2026, 4, 15, 9, 0, 0)
    alpha = User(name="Alpha Owner", email="alpha@example.com", password_hash="pw", created_at=base_time)
    beta = User(name="Beta Owner", email="beta@example.com", password_hash="pw", created_at=base_time + timedelta(minutes=1))
    db.add_all([alpha, beta])
    db.commit()
    db.refresh(alpha)
    db.refresh(beta)

    alpha_food = Category(user_id=alpha.user_id, name="Food", type="expense", created_at=base_time + timedelta(minutes=2))
    alpha_sales = Category(user_id=alpha.user_id, name="Sales", type="income", created_at=base_time + timedelta(minutes=3))
    beta_travel = Category(user_id=beta.user_id, name="Travel", type="expense", created_at=base_time + timedelta(minutes=4))
    db.add_all([alpha_food, alpha_sales, beta_travel])
    db.commit()
    db.refresh(alpha_food)
    db.refresh(alpha_sales)
    db.refresh(beta_travel)

    db.add_all(
        [
            Transaction(
                user_id=alpha.user_id,
                category_id=alpha_sales.category_id,
                amount=200.0,
                type="income",
                description="Invoice",
                date=date(2026, 4, 3),
                created_at=base_time + timedelta(minutes=5),
            ),
            Transaction(
                user_id=alpha.user_id,
                category_id=alpha_food.category_id,
                amount=80.0,
                type="expense",
                description="Lunch",
                date=date(2026, 4, 4),
                created_at=base_time + timedelta(minutes=6),
            ),
            Transaction(
                user_id=beta.user_id,
                category_id=beta_travel.category_id,
                amount=40.0,
                type="expense",
                description="Taxi",
                date=date(2026, 4, 5),
                created_at=base_time + timedelta(minutes=7),
            ),
            Budget(
                user_id=alpha.user_id,
                category_id=alpha_food.category_id,
                amount=50.0,
                month=date(2026, 4, 1),
                note="Food limit",
                created_at=base_time + timedelta(minutes=8),
            ),
            AIInsight(
                user_id=alpha.user_id,
                title="Food Spike",
                message="Food spending is above budget.",
                severity="warning",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 4, 30),
                created_at=base_time + timedelta(minutes=9),
            ),
            SystemLog(
                user_id=alpha.user_id,
                event_type="create_transaction",
                message="Alpha created a transaction",
                level="info",
                created_at=base_time + timedelta(minutes=10),
            ),
        ]
    )
    db.commit()
    return alpha, beta


def test_admin_users_sort_by_name(admin_client):
    client, db = admin_client
    _seed_users(db)

    response = client.get(
        "/admin/users",
        params={"limit": 500, "offset": 0, "sort_by": "name", "sort_order": "asc"},
    )

    assert response.status_code == 200
    assert [user["name"] for user in response.json()["users"]] == [
        "Alice Owner",
        "Bob Builder",
        "Charlie Founder",
    ]


def test_admin_users_sort_by_created_at(admin_client):
    client, db = admin_client
    _seed_users(db)

    response = client.get(
        "/admin/users",
        params={"sort_by": "created_at", "sort_order": "asc"},
    )

    assert response.status_code == 200
    assert [user["email"] for user in response.json()["users"]] == [
        "alice@example.com",
        "bob@example.com",
        "charlie@example.com",
    ]


def test_admin_categories_sort_by_name(admin_client):
    client, db = admin_client
    user = User(name="Category Owner", email="owner@example.com", password_hash="pw")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add_all(
        [
            Category(user_id=user.user_id, name="Travel", type="expense"),
            Category(user_id=user.user_id, name="Food", type="expense"),
            Category(user_id=user.user_id, name="Office", type="expense"),
        ]
    )
    db.commit()

    response = client.get(
        "/admin/categories",
        params={"limit": 500, "offset": 0, "sort_by": "name", "sort_order": "asc"},
    )

    assert response.status_code == 200
    assert [category["name"] for category in response.json()["categories"]] == [
        "Food",
        "Office",
        "Travel",
    ]


@pytest.mark.parametrize("endpoint", ["/admin/users", "/admin/categories"])
def test_admin_invalid_sort_by_returns_validation_error(admin_client, endpoint):
    client, db = admin_client
    _seed_users(db)

    response = client.get(endpoint, params={"sort_by": "password_hash"})

    assert response.status_code == 422
    assert "Unsupported sort_by" in response.json()["detail"]


def test_admin_user_overview_returns_user_specific_data(admin_client):
    client, db = admin_client
    alpha, _ = _seed_user_context_data(db)

    response = client.get(f"/admin/users/{alpha.user_id}/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "alpha@example.com"
    assert body["user"]["transactions_count"] == 2
    assert body["user"]["categories_count"] == 2
    assert body["user"]["budgets_count"] == 1
    assert body["user"]["insights_count"] == 1
    assert body["financial_summary"] == {
        "total_income": 200.0,
        "total_expense": 80.0,
        "balance": 120.0,
        "over_budget_count": 1,
    }
    assert body["recent_logs"][0]["event_type"] == "create_transaction"
    assert body["recent_insights"][0]["title"] == "Food Spike"


def test_admin_dashboard_global_and_selected_user_context(admin_client):
    client, db = admin_client
    alpha, _ = _seed_user_context_data(db)

    global_response = client.get("/admin/dashboard")
    selected_response = client.get("/admin/dashboard", params={"user_id": alpha.user_id})
    cleared_response = client.get("/admin/dashboard")

    assert global_response.status_code == 200
    assert selected_response.status_code == 200
    assert cleared_response.status_code == 200

    global_body = global_response.json()
    selected_body = selected_response.json()
    cleared_body = cleared_response.json()

    assert global_body["total_users"] == 2
    assert global_body["total_transactions"] == 3
    assert selected_body["total_users"] == 1
    assert selected_body["total_transactions"] == 2
    assert selected_body["total_categories"] == 2
    assert selected_body["total_budgets"] == 1
    assert selected_body["total_ai_insights"] == 1
    assert selected_body["recent_logs"][0]["user_email"] == "alpha@example.com"
    assert cleared_body["total_users"] == global_body["total_users"]
    assert cleared_body["total_transactions"] == global_body["total_transactions"]
