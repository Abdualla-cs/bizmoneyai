from datetime import date

from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.services.budget_metrics import list_budget_snapshots


def test_list_budget_snapshots_calculates_spend_and_status(db_session):
    user = User(name="Budget User", email="budget@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    category = Category(user_id=user.user_id, name="Operations", type="expense")
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    budget = Budget(user_id=user.user_id, category_id=category.category_id, amount=500, month=date(2026, 4, 1))
    db_session.add(budget)
    db_session.commit()

    db_session.add_all(
        [
            Transaction(
                user_id=user.user_id,
                category_id=category.category_id,
                amount=200,
                type="expense",
                description="Tools",
                date=date(2026, 4, 5),
            ),
            Transaction(
                user_id=user.user_id,
                category_id=category.category_id,
                amount=250,
                type="expense",
                description="Software",
                date=date(2026, 4, 12),
            ),
        ]
    )
    db_session.commit()

    snapshots = list_budget_snapshots(db_session, user.user_id, date(2026, 4, 1))

    assert len(snapshots) == 1
    assert snapshots[0]["category_name"] == "Operations"
    assert snapshots[0]["spent"] == 450.0
    assert snapshots[0]["remaining"] == 50.0
    assert snapshots[0]["status"] == "near_limit"
