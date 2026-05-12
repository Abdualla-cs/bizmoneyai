from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import joblib

from app.models.ai_insight import AIInsight
from app.services.insight_ranker import (
    MODEL_FAMILY,
    MODEL_FEATURE_COLUMNS,
    PRIORITY_LEVELS,
    InsightRanker,
)


class ScenarioPriorityModel:
    def predict(self, rows: Any) -> list[float]:
        predictions: list[float] = []
        for _index, row in rows.iterrows():
            if row["severity"] == "critical" and float(row["is_fraud_related"]) == 1.0:
                predictions.append(97.0)
            elif row["severity"] == "critical":
                predictions.append(92.0)
            elif float(row["recurrence_count"]) >= 2.0:
                predictions.append(78.0)
            elif row["severity"] == "info":
                predictions.append(42.0)
            else:
                predictions.append(64.0)
        return predictions


def _write_artifact(tmp_path: Path, model: object | None = None) -> Path:
    model_path = tmp_path / "insight_ranker.joblib"
    joblib.dump(
        {
            "model": model or ScenarioPriorityModel(),
            "model_family": MODEL_FAMILY,
            "feature_columns": list(MODEL_FEATURE_COLUMNS),
            "metadata": {
                "model_family": MODEL_FAMILY,
                "feature_columns": list(MODEL_FEATURE_COLUMNS),
            },
        },
        model_path,
    )
    return model_path


def _insight(
    *,
    insight_id: int,
    rule_id: str,
    severity: str,
    metadata_json: dict[str, Any] | None,
    created_at: datetime,
) -> AIInsight:
    return AIInsight(
        insight_id=insight_id,
        user_id=1,
        rule_id=rule_id,
        title=f"Insight {insight_id}",
        message="Test insight",
        severity=severity,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        metadata_json=metadata_json,
        created_at=created_at,
    )


def test_service_loads_when_artifact_exists(tmp_path: Path) -> None:
    ranker = InsightRanker(model_path=_write_artifact(tmp_path))

    assert ranker.is_ready() is True


def test_service_safely_works_when_artifact_missing(tmp_path: Path) -> None:
    ranker = InsightRanker(model_path=tmp_path / "missing.joblib")
    insight = _insight(
        insight_id=1,
        rule_id="expense_ratio",
        severity="info",
        metadata_json=None,
        created_at=datetime(2026, 5, 5, 12, 0, 0),
    )

    result = ranker.score_insight(insight)

    assert ranker.is_ready() is False
    assert isinstance(result.priority_score, float)
    assert result.priority_level in PRIORITY_LEVELS


def test_critical_fraud_insight_ranks_above_info_insight(tmp_path: Path) -> None:
    ranker = InsightRanker(model_path=_write_artifact(tmp_path))
    fraud = _insight(
        insight_id=1,
        rule_id="ml_unusual_transaction",
        severity="critical",
        metadata_json={"fraud_probability": 0.94, "scope_key": "transaction:1"},
        created_at=datetime(2026, 5, 6, 9, 0, 0),
    )
    info = _insight(
        insight_id=2,
        rule_id="expense_ratio",
        severity="info",
        metadata_json={"expense_ratio": 0.08},
        created_at=datetime(2026, 5, 6, 10, 0, 0),
    )

    ranked = ranker.rank_insights([info, fraud])

    assert ranked[0].insight is fraud
    assert ranked[0].priority_score > ranked[1].priority_score


def test_priority_output_fields_are_valid(tmp_path: Path) -> None:
    ranker = InsightRanker(model_path=_write_artifact(tmp_path))
    insight = _insight(
        insight_id=1,
        rule_id="profit_drop_percent",
        severity="critical",
        metadata_json={"previous_profit": 10_000.0, "current_profit": 2_000.0, "profit_drop_percent": 80.0},
        created_at=datetime(2026, 5, 7, 8, 0, 0),
    )

    result = ranker.score_insight(insight)

    assert isinstance(result.priority_score, float)
    assert result.priority_level in PRIORITY_LEVELS
    assert result.priority_reason in {
        "High financial impact",
        "Critical severity",
        "Repeated issue",
        "Recent insight",
        "ML-detected risk",
    }


def test_rank_insights_returns_sorted_results(tmp_path: Path) -> None:
    ranker = InsightRanker(model_path=_write_artifact(tmp_path))
    insights = [
        _insight(
            insight_id=1,
            rule_id="expense_ratio",
            severity="info",
            metadata_json={"expense_ratio": 0.1},
            created_at=datetime(2026, 5, 1, 8, 0, 0),
        ),
        _insight(
            insight_id=2,
            rule_id="consecutive_budget_overspend",
            severity="warning",
            metadata_json={"consecutive_overspend_count": 4, "budget_spent": 900.0, "budget_amount": 500.0},
            created_at=datetime(2026, 5, 2, 8, 0, 0),
        ),
        _insight(
            insight_id=3,
            rule_id="ml_unusual_transaction",
            severity="critical",
            metadata_json={"fraud_probability": 0.9},
            created_at=datetime(2026, 5, 3, 8, 0, 0),
        ),
    ]

    ranked = ranker.rank_insights(insights)

    assert [item.priority_score for item in ranked] == sorted(
        [item.priority_score for item in ranked],
        reverse=True,
    )
    assert ranked[0].insight.rule_id == "ml_unusual_transaction"


def test_missing_metadata_does_not_crash(tmp_path: Path) -> None:
    ranker = InsightRanker(model_path=_write_artifact(tmp_path))
    insight = _insight(
        insight_id=1,
        rule_id="expense_ratio",
        severity="info",
        metadata_json=None,
        created_at=datetime(2026, 5, 1, 8, 0, 0),
    )

    result = ranker.score_insight(insight)

    assert isinstance(result.priority_score, float)
    assert result.priority_level in PRIORITY_LEVELS


def test_fallback_orders_by_severity_fraud_recurrence_impact_and_newness(tmp_path: Path) -> None:
    ranker = InsightRanker(model_path=tmp_path / "missing.joblib")
    info = _insight(
        insight_id=1,
        rule_id="expense_ratio",
        severity="info",
        metadata_json={"current_expense": 100_000.0},
        created_at=datetime(2026, 5, 4, 8, 0, 0),
    )
    repeated = _insight(
        insight_id=2,
        rule_id="consecutive_budget_overspend",
        severity="warning",
        metadata_json={"consecutive_overspend_count": 4, "budget_spent": 800.0, "budget_amount": 500.0},
        created_at=datetime(2026, 5, 3, 8, 0, 0),
    )
    fraud = _insight(
        insight_id=3,
        rule_id="ml_unusual_transaction",
        severity="critical",
        metadata_json={"fraud_probability": 0.9},
        created_at=datetime(2026, 5, 2, 8, 0, 0),
    )

    ranked = ranker.rank_insights([info, repeated, fraud])

    assert [item.insight for item in ranked] == [fraud, repeated, info]
