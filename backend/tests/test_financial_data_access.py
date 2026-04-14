from datetime import date, datetime

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.data_access import extract_training_data_bundle
from app.db.session import get_db
from app.main import app
from app.models.ai_insight import AIInsight
from app.models.budget import Budget
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User


def test_financial_data_access_supports_timeseries_and_training_extraction(db_session):
    user = User(name="Data User", email="data-user@example.com", password_hash="x")
    other_user = User(name="Other User", email="other-data@example.com", password_hash="x")
    db_session.add_all([user, other_user])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(other_user)

    food = Category(user_id=user.user_id, name="Food", type="expense")
    sales = Category(user_id=user.user_id, name="Sales", type="income")
    other_category = Category(user_id=other_user.user_id, name="Travel", type="expense")
    db_session.add_all([food, sales, other_category])
    db_session.commit()
    db_session.refresh(food)
    db_session.refresh(sales)
    db_session.refresh(other_category)

    db_session.add_all(
        [
            Transaction(
                user_id=user.user_id,
                category_id=food.category_id,
                amount=10.0,
                type="expense",
                description="Lunch",
                date=date(2026, 3, 5),
            ),
            Transaction(
                user_id=user.user_id,
                category_id=sales.category_id,
                amount=100.0,
                type="income",
                description="Invoice",
                date=date(2026, 3, 10),
            ),
            Transaction(
                user_id=user.user_id,
                category_id=food.category_id,
                amount=25.0,
                type="expense",
                description="Dinner",
                date=date(2026, 4, 2),
            ),
            Transaction(
                user_id=other_user.user_id,
                category_id=other_category.category_id,
                amount=77.0,
                type="expense",
                description="Taxi",
                date=date(2026, 4, 2),
            ),
            Budget(
                user_id=user.user_id,
                category_id=food.category_id,
                amount=50.0,
                month=date(2026, 3, 1),
                note="March food",
            ),
            Budget(
                user_id=user.user_id,
                category_id=food.category_id,
                amount=60.0,
                month=date(2026, 4, 1),
                note="April food",
            ),
            Budget(
                user_id=other_user.user_id,
                category_id=other_category.category_id,
                amount=80.0,
                month=date(2026, 4, 1),
                note="Other budget",
            ),
            AIInsight(
                user_id=user.user_id,
                title="March Warning",
                message="March spend is high",
                severity="warning",
                period_start=date(2026, 3, 1),
                period_end=date(2026, 3, 31),
                created_at=datetime(2026, 3, 15, 9, 30, 0),
            ),
            AIInsight(
                user_id=user.user_id,
                title="April Info",
                message="April is on track",
                severity="info",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 4, 30),
                created_at=datetime(2026, 4, 3, 11, 0, 0),
            ),
            AIInsight(
                user_id=other_user.user_id,
                title="Other Critical",
                message="Other user issue",
                severity="critical",
                period_start=date(2026, 4, 1),
                period_end=date(2026, 4, 30),
                created_at=datetime(2026, 4, 4, 8, 0, 0),
            ),
        ]
    )
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    try:
        transactions_response = client.get("/transactions", params={"date_from": "2026-04-01"})
        assert transactions_response.status_code == 200
        transactions_body = transactions_response.json()
        assert len(transactions_body) == 1
        assert transactions_body[0]["description"] == "Dinner"

        transaction_series_response = client.get("/transactions/timeseries", params={"granularity": "month"})
        assert transaction_series_response.status_code == 200
        transaction_series = transaction_series_response.json()
        assert transaction_series == [
            {
                "bucket": "2026-03-01",
                "transactions_count": 2,
                "income_total": 100.0,
                "expense_total": 10.0,
                "net_total": 90.0,
            },
            {
                "bucket": "2026-04-01",
                "transactions_count": 1,
                "income_total": 0.0,
                "expense_total": 25.0,
                "net_total": -25.0,
            },
        ]

        budgets_response = client.get("/budgets", params={"month_from": "2026-04-01"})
        assert budgets_response.status_code == 200
        budgets_body = budgets_response.json()
        assert len(budgets_body) == 1
        assert budgets_body[0]["month"] == "2026-04-01"
        assert budgets_body[0]["spent"] == 25.0

        budget_series_response = client.get("/budgets/timeseries")
        assert budget_series_response.status_code == 200
        assert budget_series_response.json() == [
            {
                "bucket": "2026-03-01",
                "budgets_count": 1,
                "total_budgeted": 50.0,
                "total_spent": 10.0,
                "over_budget_count": 0,
            },
            {
                "bucket": "2026-04-01",
                "budgets_count": 1,
                "total_budgeted": 60.0,
                "total_spent": 25.0,
                "over_budget_count": 0,
            },
        ]

        insights_response = client.get("/ai/insights", params={"date_from": "2026-04-01", "severity": "info"})
        assert insights_response.status_code == 200
        insights_body = insights_response.json()
        assert len(insights_body) == 1
        assert insights_body[0]["title"] == "April Info"

        insight_series_response = client.get("/ai/insights/timeseries", params={"granularity": "month"})
        assert insight_series_response.status_code == 200
        assert insight_series_response.json() == [
            {
                "bucket": "2026-03-01",
                "insights_count": 1,
                "info_count": 0,
                "warning_count": 1,
                "critical_count": 0,
            },
            {
                "bucket": "2026-04-01",
                "insights_count": 1,
                "info_count": 1,
                "warning_count": 0,
                "critical_count": 0,
            },
        ]

        bundle = extract_training_data_bundle(
            db_session,
            user_id=user.user_id,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 30),
        )
        assert len(bundle.transactions) == 1
        assert bundle.transactions[0].category_name == "Food"
        assert len(bundle.budgets) == 1
        assert bundle.budgets[0].month == date(2026, 4, 1)
        assert len(bundle.insights) == 1
        assert bundle.insights[0].title == "April Info"
    finally:
        app.dependency_overrides.clear()
