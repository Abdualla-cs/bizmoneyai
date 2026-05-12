from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

import app.api.ai as ai_api_module
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.ai_insight import AIInsight
from app.models.user import User
from app.services.insight_ranker import InsightRanker


def _client(db_session, user: User | None = None) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    if user is not None:
        client.cookies.set("access_token", create_access_token(str(user.user_id)))
    return client


def _user(db_session, *, email: str = "ranked-insights@example.com") -> User:
    user = User(name="Ranked Insight User", email=email, password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _insight(
    db_session,
    *,
    user: User,
    rule_id: str,
    title: str,
    severity: str,
    created_at: datetime,
    metadata_json: dict | None = None,
) -> AIInsight:
    insight = AIInsight(
        user_id=user.user_id,
        rule_id=rule_id,
        title=title,
        message=f"{title} message",
        severity=severity,
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        created_at=created_at,
        metadata_json=metadata_json,
    )
    db_session.add(insight)
    db_session.commit()
    db_session.refresh(insight)
    return insight


def _force_fallback_ranker(monkeypatch, tmp_path: Path) -> None:
    fallback_ranker = InsightRanker(model_path=tmp_path / "missing_insight_ranker.joblib")
    monkeypatch.setattr(ai_api_module.insight_ranker, "rank_insights", fallback_ranker.rank_insights)


def test_ranked_insights_requires_user_auth(db_session):
    client = _client(db_session)

    try:
        response = client.get("/ai/insights/ranked")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_ranked_insights_returns_existing_insights_with_priority_fields(db_session, tmp_path: Path, monkeypatch) -> None:
    _force_fallback_ranker(monkeypatch, tmp_path)
    user = _user(db_session)
    _insight(
        db_session,
        user=user,
        rule_id="expense_ratio",
        title="Expense Ratio",
        severity="info",
        created_at=datetime(2026, 4, 2, 10, 0, 0),
        metadata_json={"expense_ratio": 0.12},
    )
    client = _client(db_session, user)

    try:
        response = client.get("/ai/insights/ranked")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["title"] == "Expense Ratio"
        assert isinstance(body[0]["priority_score"], float)
        assert body[0]["priority_level"] in {"low", "medium", "high", "critical"}
        assert isinstance(body[0]["priority_reason"], str)
    finally:
        app.dependency_overrides.clear()


def test_ranked_insights_sorts_high_priority_before_low_priority(db_session, tmp_path: Path, monkeypatch) -> None:
    _force_fallback_ranker(monkeypatch, tmp_path)
    user = _user(db_session)
    low = _insight(
        db_session,
        user=user,
        rule_id="expense_ratio",
        title="Small Info",
        severity="info",
        created_at=datetime(2026, 4, 4, 10, 0, 0),
        metadata_json={"expense_ratio": 0.05},
    )
    high = _insight(
        db_session,
        user=user,
        rule_id="ml_unusual_transaction",
        title="Critical Fraud",
        severity="critical",
        created_at=datetime(2026, 4, 1, 10, 0, 0),
        metadata_json={"fraud_probability": 0.94, "amount": 90_000.0},
    )
    client = _client(db_session, user)

    try:
        response = client.get("/ai/insights/ranked")
        assert response.status_code == 200
        body = response.json()
        assert [item["insight_id"] for item in body] == [high.insight_id, low.insight_id]
        assert body[0]["priority_score"] > body[1]["priority_score"]
    finally:
        app.dependency_overrides.clear()


def test_ranked_insights_fallback_works_when_model_unavailable(db_session, tmp_path: Path, monkeypatch) -> None:
    _force_fallback_ranker(monkeypatch, tmp_path)
    user = _user(db_session)
    _insight(
        db_session,
        user=user,
        rule_id="income_drop_percent",
        title="Income Drop",
        severity="warning",
        created_at=datetime(2026, 4, 5, 10, 0, 0),
        metadata_json=None,
    )
    client = _client(db_session, user)

    try:
        response = client.get("/ai/insights/ranked")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["priority_score"] >= 0.0
        assert body[0]["priority_reason"]
    finally:
        app.dependency_overrides.clear()


def test_ranked_insights_includes_rule_based_and_ml_created_insights(db_session, tmp_path: Path, monkeypatch) -> None:
    _force_fallback_ranker(monkeypatch, tmp_path)
    user = _user(db_session, email="ranked-all-ml@example.com")
    created_at = datetime(2026, 4, 5, 10, 0, 0)
    expected_rule_ids = {
        "expense_ratio",
        "ml_unusual_transaction",
        "ml_spending_forecast_risk",
        "ml_budget_recommendation",
    }
    for index, rule_id in enumerate(sorted(expected_rule_ids), start=1):
        _insight(
            db_session,
            user=user,
            rule_id=rule_id,
            title=f"Insight {index}",
            severity="warning",
            created_at=created_at,
            metadata_json={"source": rule_id.replace("ml_", "")} if rule_id.startswith("ml_") else None,
        )
    client = _client(db_session, user)

    try:
        response = client.get("/ai/insights/ranked")
        assert response.status_code == 200
        body = response.json()
        assert {item["rule_id"] for item in body} == expected_rule_ids
        assert all("priority_score" in item for item in body)
    finally:
        app.dependency_overrides.clear()


def test_ranked_insights_only_returns_current_user_and_honors_filters(db_session, tmp_path: Path, monkeypatch) -> None:
    _force_fallback_ranker(monkeypatch, tmp_path)
    user = _user(db_session, email="ranked-owner@example.com")
    other_user = _user(db_session, email="ranked-other@example.com")
    _insight(
        db_session,
        user=user,
        rule_id="expense_ratio",
        title="Owner Warning",
        severity="warning",
        created_at=datetime(2026, 4, 5, 10, 0, 0),
        metadata_json={"expense_ratio": 0.7},
    )
    _insight(
        db_session,
        user=user,
        rule_id="income_drop_percent",
        title="Owner Info",
        severity="info",
        created_at=datetime(2026, 3, 5, 10, 0, 0),
        metadata_json={"income_drop_percent": 5.0},
    )
    _insight(
        db_session,
        user=other_user,
        rule_id="ml_unusual_transaction",
        title="Other Critical",
        severity="critical",
        created_at=datetime(2026, 4, 6, 10, 0, 0),
        metadata_json={"fraud_probability": 0.99},
    )
    client = _client(db_session, user)

    try:
        response = client.get(
            "/ai/insights/ranked",
            params={"date_from": "2026-04-01", "severity": "warning"},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["title"] == "Owner Warning"
        assert body[0]["user_id"] == user.user_id
    finally:
        app.dependency_overrides.clear()


def test_existing_ai_insights_behavior_is_not_broken(db_session, tmp_path: Path, monkeypatch) -> None:
    _force_fallback_ranker(monkeypatch, tmp_path)
    user = _user(db_session)
    older = _insight(
        db_session,
        user=user,
        rule_id="ml_unusual_transaction",
        title="Older Critical",
        severity="critical",
        created_at=datetime(2026, 4, 1, 10, 0, 0),
        metadata_json={"fraud_probability": 0.99},
    )
    newer = _insight(
        db_session,
        user=user,
        rule_id="expense_ratio",
        title="Newer Info",
        severity="info",
        created_at=datetime(2026, 4, 6, 10, 0, 0),
        metadata_json={"expense_ratio": 0.1},
    )
    client = _client(db_session, user)

    try:
        response = client.get("/ai/insights")
        assert response.status_code == 200
        body = response.json()
        assert [item["insight_id"] for item in body] == [newer.insight_id, older.insight_id]
        assert "priority_score" not in body[0]
        assert "priority_level" not in body[0]
        assert "priority_reason" not in body[0]
    finally:
        app.dependency_overrides.clear()
