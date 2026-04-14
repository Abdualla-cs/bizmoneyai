from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.budget import Budget
from app.models.category import Category
from app.models.system_log import SystemLog
from app.models.transaction import Transaction
from app.models.user import User


def test_transaction_rejects_mismatched_category_type(db_session):
    user = User(name="User", email="type-check@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    income_category = Category(user_id=user.user_id, name="Sales", type="income")
    db_session.add(income_category)
    db_session.commit()
    db_session.refresh(income_category)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    response = client.post(
        "/transactions",
        json={
            "category_id": income_category.category_id,
            "amount": 25,
            "type": "expense",
            "description": "Should fail",
            "date": "2026-04-01",
        },
    )

    try:
        assert response.status_code == 400
        assert "only supports income transactions" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("amount", [0, -5])
def test_transaction_create_rejects_non_positive_amounts(db_session, amount):
    user = User(name="Amount User", email=f"amount-create-{amount}@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Office", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    response = client.post(
        "/transactions",
        json={
            "category_id": category.category_id,
            "amount": amount,
            "type": "expense",
            "description": "Invalid amount",
            "date": "2026-04-01",
        },
    )

    try:
        assert response.status_code == 422
        assert "greater than 0" in str(response.json()["detail"])
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("amount", [0, -10])
def test_transaction_update_rejects_non_positive_amounts(db_session, amount):
    user = User(name="Amount Update User", email=f"amount-update-{amount}@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Travel", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    transaction = Transaction(
        user_id=user.user_id,
        category_id=category.category_id,
        amount=25,
        type="expense",
        description="Original",
        date=date(2026, 4, 1),
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    response = client.put(
        f"/transactions/{transaction.transaction_id}",
        json={"amount": amount},
    )

    try:
        assert response.status_code == 422
        assert "greater than 0" in str(response.json()["detail"])
    finally:
        app.dependency_overrides.clear()


def test_transaction_allows_positive_amounts_for_create_and_update(db_session):
    user = User(name="Valid Amount User", email="valid-amount@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Consulting", type="income")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    create_response = client.post(
        "/transactions",
        json={
            "category_id": category.category_id,
            "amount": 100,
            "type": "income",
            "description": "Consulting fee",
            "date": "2026-04-01",
        },
    )

    try:
        assert create_response.status_code == 201
        transaction_id = create_response.json()["transaction_id"]

        update_response = client.put(
            f"/transactions/{transaction_id}",
            json={"amount": 150},
        )
        assert update_response.status_code == 200
        assert update_response.json()["amount"] == 150
    finally:
        app.dependency_overrides.clear()


def test_transaction_import_rejects_invalid_category_type_rows(db_session):
    user = User(name="User", email="import-check@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    income_category = Category(user_id=user.user_id, name="Sales", type="income")
    db_session.add(income_category)
    db_session.commit()
    db_session.refresh(income_category)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    response = client.post(
        "/transactions/import-file",
        files={
            "file": (
                "transactions.csv",
                "category_id,amount,type,description,date\n"
                f"{income_category.category_id},40,expense,Invalid import,2026-04-01\n",
                "text/csv",
            )
        },
    )

    try:
        assert response.status_code == 400
        assert "only supports income transactions" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_transaction_import_creates_and_reuses_categories_by_name(db_session):
    user = User(name="Importer", email="category-import@example.com", password_hash="x")
    other_user = User(name="Other User", email="other-import@example.com", password_hash="x")
    db_session.add_all([user, other_user])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(other_user)

    existing_category = Category(user_id=user.user_id, name="Meals", type="expense")
    other_user_category = Category(user_id=other_user.user_id, name="Travel", type="expense")
    db_session.add_all([existing_category, other_user_category])
    db_session.commit()
    db_session.refresh(existing_category)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    response = client.post(
        "/transactions/import-csv",
        files={
            "file": (
                "transactions.csv",
                "category_name,amount,type,description,date\n"
                "meals,12.5,expense,Team lunch,2026-04-01\n"
                "Travel,18,expense,Taxi,2026-04-02\n"
                "travel,22,expense,Train,2026-04-03\n",
                "text/csv",
            )
        },
    )

    try:
        assert response.status_code == 200
        body = response.json()
        assert body["imported_count"] == 3
        assert body["skipped_count"] == 0
        assert body["rejected_rows"] == []
        assert body["transactions"][0]["category_id"] == existing_category.category_id

        user_categories = (
            db_session.query(Category)
            .filter(Category.user_id == user.user_id)
            .order_by(Category.category_id.asc())
            .all()
        )
        assert len(user_categories) == 2
        assert {category.name for category in user_categories} == {"Meals", "Travel"}

        travel_category = next(category for category in user_categories if category.name == "Travel")
        assert travel_category.type == "expense"
        assert body["transactions"][1]["category_id"] == travel_category.category_id
        assert body["transactions"][2]["category_id"] == travel_category.category_id

        creation_logs = (
            db_session.query(SystemLog)
            .filter(SystemLog.user_id == user.user_id, SystemLog.event_type == "create_category")
            .order_by(SystemLog.log_id.asc())
            .all()
        )
        assert len(creation_logs) == 1
        assert "Travel" in creation_logs[0].message
        assert creation_logs[0].metadata_json == {
            "user_id": user.user_id,
            "admin_id": None,
            "entity_id": travel_category.category_id,
            "category_name": "Travel",
            "category_type": "expense",
            "source": "transaction_import",
        }

        import_log = (
            db_session.query(SystemLog)
            .filter(SystemLog.user_id == user.user_id, SystemLog.event_type == "import_transactions")
            .one()
        )
        assert import_log.metadata_json == {
            "user_id": user.user_id,
            "admin_id": None,
            "entity_id": None,
            "file_name": "transactions.csv",
            "imported_count": 3,
            "skipped_count": 0,
            "file_type": "csv",
        }
    finally:
        app.dependency_overrides.clear()


def test_transaction_import_skips_duplicate_rows_in_same_file(db_session):
    user = User(name="Duplicate Import User", email="duplicate-import@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Meals", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    response = client.post(
        "/transactions/import-file",
        files={
            "file": (
                "transactions.csv",
                "category_name,amount,type,description,date\n"
                "Meals,12.5,expense,Team lunch,2026-04-01\n"
                "meals,12.5,expense,Team lunch,2026-04-01\n"
                "Meals,15,expense,Client lunch,2026-04-02\n",
                "text/csv",
            )
        },
    )

    try:
        assert response.status_code == 200
        body = response.json()
        assert body["imported_count"] == 2
        assert body["skipped_count"] == 1
        assert body["rejected_rows"] == [
            {"row_number": 3, "reason": "Duplicate row in import file"}
        ]
        assert db_session.query(Transaction).filter(Transaction.user_id == user.user_id).count() == 2

        import_log = (
            db_session.query(SystemLog)
            .filter(SystemLog.user_id == user.user_id, SystemLog.event_type == "import_transactions")
            .one()
        )
        assert import_log.metadata_json == {
            "user_id": user.user_id,
            "admin_id": None,
            "entity_id": None,
            "file_name": "transactions.csv",
            "imported_count": 2,
            "skipped_count": 1,
            "file_type": "csv",
        }
    finally:
        app.dependency_overrides.clear()


def test_transaction_import_file_rejects_rows_without_category_id_or_name(db_session):
    user = User(name="Missing Category", email="missing-category@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    response = client.post(
        "/transactions/import-file",
        files={
            "file": (
                "transactions.csv",
                "category_id,category_name,amount,type,description,date\n"
                ",,40,expense,No category,2026-04-01\n",
                "text/csv",
            )
        },
    )

    try:
        assert response.status_code == 400
        assert response.json()["detail"] == "Row 2: category_id or category_name is required"
        assert db_session.query(Transaction).filter(Transaction.user_id == user.user_id).count() == 0
        assert db_session.query(Category).filter(Category.user_id == user.user_id).count() == 0
        assert db_session.query(SystemLog).filter(SystemLog.user_id == user.user_id).count() == 0
    finally:
        app.dependency_overrides.clear()


def test_category_delete_returns_400_when_records_exist(db_session):
    user = User(name="User", email="delete-guard@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Food", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    db_session.add(
        Transaction(
            user_id=user.user_id,
            category_id=category.category_id,
            amount=10,
            type="expense",
            date=date(2026, 4, 1),
        )
    )
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    response = client.delete(f"/categories/{category.category_id}")

    try:
        assert response.status_code == 400
        assert "Delete linked transactions and budgets" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_category_type_update_rejects_conflicting_existing_records(db_session):
    user = User(name="User", email="update-guard@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Food", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    db_session.add_all(
        [
            Transaction(
                user_id=user.user_id,
                category_id=category.category_id,
                amount=10,
                type="expense",
                date=date(2026, 4, 1),
            ),
            Budget(
                user_id=user.user_id,
                category_id=category.category_id,
                amount=50,
                month=date(2026, 4, 1),
            ),
        ]
    )
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    response = client.put(
        f"/categories/{category.category_id}",
        json={"type": "income"},
    )

    try:
        assert response.status_code == 400
        assert "cannot be changed to income" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_category_create_and_delete_write_audit_logs(db_session):
    user = User(name="Category Audit", email="category-audit@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    create_response = client.post(
        "/categories",
        json={"name": "Subscriptions", "type": "expense"},
    )

    try:
        assert create_response.status_code == 201
        category_id = create_response.json()["category_id"]

        delete_response = client.delete(f"/categories/{category_id}")
        assert delete_response.status_code == 204

        logs = db_session.query(SystemLog).filter(SystemLog.user_id == user.user_id).order_by(SystemLog.log_id.asc()).all()
        assert [log.event_type for log in logs] == ["create_category", "delete_category"]
        assert logs[0].metadata_json == {
            "user_id": user.user_id,
            "admin_id": None,
            "entity_id": category_id,
            "category_name": "Subscriptions",
            "category_type": "expense",
            "source": "category_api",
        }
        assert logs[1].metadata_json == {
            "user_id": user.user_id,
            "admin_id": None,
            "entity_id": category_id,
            "category_name": "Subscriptions",
            "category_type": "expense",
            "source": "category_api",
        }
    finally:
        app.dependency_overrides.clear()


def test_category_names_are_case_insensitive_per_user(db_session):
    first_user = User(name="First User", email="first-category@example.com", password_hash="x")
    second_user = User(name="Second User", email="second-category@example.com", password_hash="x")
    db_session.add_all([first_user, second_user])
    db_session.commit()
    db_session.refresh(first_user)
    db_session.refresh(second_user)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    try:
        client.cookies.set("access_token", create_access_token(str(first_user.user_id)))
        first_response = client.post(
            "/categories",
            json={"name": "Travel", "type": "expense"},
        )
        assert first_response.status_code == 201

        duplicate_response = client.post(
            "/categories",
            json={"name": "travel", "type": "expense"},
        )
        assert duplicate_response.status_code == 400
        assert duplicate_response.json()["detail"] == "Category name already exists"

        client.cookies.set("access_token", create_access_token(str(second_user.user_id)))
        other_user_response = client.post(
            "/categories",
            json={"name": "TRAVEL", "type": "expense"},
        )
        assert other_user_response.status_code == 201
    finally:
        app.dependency_overrides.clear()


def test_transaction_crud_writes_audit_logs(db_session):
    user = User(name="Transaction Audit", email="transaction-audit@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Operations", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    create_response = client.post(
        "/transactions",
        json={
            "category_id": category.category_id,
            "amount": 45,
            "type": "expense",
            "description": "Printer toner",
            "date": "2026-04-10",
        },
    )

    try:
        assert create_response.status_code == 201
        transaction_id = create_response.json()["transaction_id"]

        update_response = client.put(
            f"/transactions/{transaction_id}",
            json={
                "amount": 50,
                "description": "Printer toner refill",
            },
        )
        assert update_response.status_code == 200

        delete_response = client.delete(f"/transactions/{transaction_id}")
        assert delete_response.status_code == 204

        logs = (
            db_session.query(SystemLog)
            .filter(SystemLog.user_id == user.user_id)
            .filter(SystemLog.event_type.in_(["create_transaction", "update_transaction", "delete_transaction"]))
            .order_by(SystemLog.log_id.asc())
            .all()
        )
        assert [log.event_type for log in logs] == [
            "create_transaction",
            "update_transaction",
            "delete_transaction",
        ]
        assert logs[0].metadata_json == {
            "user_id": user.user_id,
            "admin_id": None,
            "entity_id": transaction_id,
            "category_id": category.category_id,
            "category_name": "Operations",
            "amount": 45,
            "type": "expense",
            "description": "Printer toner",
            "date": "2026-04-10",
        }
        assert logs[1].metadata_json == {
            "user_id": user.user_id,
            "admin_id": None,
            "entity_id": transaction_id,
            "category_id": category.category_id,
            "category_name": "Operations",
            "amount": 50,
            "type": "expense",
            "description": "Printer toner refill",
            "date": "2026-04-10",
        }
        assert logs[2].metadata_json == {
            "user_id": user.user_id,
            "admin_id": None,
            "entity_id": transaction_id,
            "category_id": category.category_id,
            "category_name": "Operations",
            "amount": 50,
            "type": "expense",
            "description": "Printer toner refill",
            "date": "2026-04-10",
        }
    finally:
        app.dependency_overrides.clear()
