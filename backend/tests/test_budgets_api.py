from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.budget import Budget
from app.models.category import Category
from app.models.system_log import SystemLog
from app.models.user import User


def test_create_budget_api_returns_budget_snapshot(db_session):
    user = User(name="Budget API", email="budget-api@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Office Rent", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    token = create_access_token(str(user.user_id))
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", token)

    response = client.post(
        "/budgets",
        json={
            "category_id": category.category_id,
            "amount": 1300,
            "month": "2026-04-17",
            "note": "April plan",
        },
    )

    try:
        assert response.status_code == 201
        body = response.json()
        assert body["category_name"] == "Office Rent"
        assert body["month"] == "2026-04-01"
        assert body["amount"] == 1300
        assert body["spent"] == 0
    finally:
        app.dependency_overrides.clear()


def test_create_budget_rejects_duplicate_month_year_even_for_legacy_non_normalized_rows(db_session):
    user = User(name="Budget Duplicate", email="budget-duplicate@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Marketing", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    db_session.add(
        Budget(
            user_id=user.user_id,
            category_id=category.category_id,
            amount=200,
            month=date(2026, 4, 17),
            note="Legacy day value",
        )
    )
    db_session.commit()

    token = create_access_token(str(user.user_id))
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", token)

    response = client.post(
        "/budgets",
        json={
            "category_id": category.category_id,
            "amount": 300,
            "month": "2026-04-01",
            "note": "April retry",
        },
    )

    try:
        assert response.status_code == 400
        assert response.json()["detail"] == "Budget already exists for this category and month"
    finally:
        app.dependency_overrides.clear()


def test_create_budget_handles_integrity_error_gracefully(db_session, monkeypatch):
    user = User(name="Budget Integrity", email="budget-integrity@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Software", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    original_commit = db_session.commit

    def fake_commit():
        raise IntegrityError(
            statement="INSERT INTO budgets",
            params={},
            orig=Exception("duplicate key value violates unique constraint 'uq_budgets_user_category_month_year'"),
        )

    monkeypatch.setattr(db_session, "commit", fake_commit)

    token = create_access_token(str(user.user_id))
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", token)

    response = client.post(
        "/budgets",
        json={
            "category_id": category.category_id,
            "amount": 99,
            "month": "2026-04-01",
            "note": None,
        },
    )

    try:
        assert response.status_code == 400
        assert response.json()["detail"] == "Budget already exists for this category and month"
    finally:
        monkeypatch.setattr(db_session, "commit", original_commit)
        app.dependency_overrides.clear()


def test_budget_create_and_update_write_audit_logs(db_session):
    user = User(name="Budget Audit", email="budget-audit@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Operations", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    token = create_access_token(str(user.user_id))
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", token)

    create_response = client.post(
        "/budgets",
        json={
            "category_id": category.category_id,
            "amount": 450,
            "month": "2026-04-01",
            "note": "Initial plan",
        },
    )

    try:
        assert create_response.status_code == 201
        budget_id = create_response.json()["budget_id"]

        update_response = client.put(
            f"/budgets/{budget_id}",
            json={
                "amount": 500,
                "note": "Updated plan",
            },
        )
        assert update_response.status_code == 200

        logs = db_session.query(SystemLog).filter(SystemLog.user_id == user.user_id).order_by(SystemLog.log_id.asc()).all()
        assert [log.event_type for log in logs] == ["create_budget", "update_budget"]
        assert logs[0].metadata_json == {
            "user_id": user.user_id,
            "admin_id": None,
            "entity_id": budget_id,
            "category_id": category.category_id,
            "category_name": "Operations",
            "amount": 450.0,
            "month": "2026-04-01",
        }
        assert logs[1].metadata_json == {
            "user_id": user.user_id,
            "admin_id": None,
            "entity_id": budget_id,
            "category_id": category.category_id,
            "category_name": "Operations",
            "amount": 500.0,
            "month": "2026-04-01",
        }
    finally:
        app.dependency_overrides.clear()
