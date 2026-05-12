from __future__ import annotations

import csv
from pathlib import Path

import joblib
import pytest

from app.ml.insight_ranking.train_insight_ranker import MODEL_FAMILY, train
from app.ml.insight_ranking.validate_insight_ranker import (
    load_artifact,
    score_scenarios,
    validate_artifact_contract,
    validate_insight_ranker,
)


FIELDNAMES = [
    "insight_id",
    "rule_id",
    "title",
    "severity",
    "category_name",
    "impact_amount",
    "impact_ratio",
    "recurrence_count",
    "days_since_generated",
    "period_days",
    "confidence_score",
    "is_ml_generated",
    "is_budget_related",
    "is_fraud_related",
    "is_forecast_related",
    "is_income_related",
    "is_profit_related",
    "is_expense_related",
    "business_profile",
    "company_size",
    "generated_at",
    "period_start",
    "period_end",
    "priority_level",
    "priority_score",
]


def _row(
    index: int,
    *,
    rule_id: str,
    severity: str,
    category_name: str,
    impact_amount: float,
    impact_ratio: float,
    recurrence_count: float,
    confidence_score: float,
    flags: dict[str, int],
    priority_score: float,
) -> dict[str, object]:
    return {
        "insight_id": index,
        "rule_id": rule_id,
        "title": f"Insight {index}",
        "severity": severity,
        "category_name": category_name,
        "impact_amount": impact_amount,
        "impact_ratio": impact_ratio,
        "recurrence_count": recurrence_count,
        "days_since_generated": index % 20,
        "period_days": 30 if index % 3 else 7,
        "confidence_score": confidence_score,
        "is_ml_generated": flags.get("ml", 0),
        "is_budget_related": flags.get("budget", 0),
        "is_fraud_related": flags.get("fraud", 0),
        "is_forecast_related": flags.get("forecast", 0),
        "is_income_related": flags.get("income", 0),
        "is_profit_related": flags.get("profit", 0),
        "is_expense_related": flags.get("expense", 1),
        "business_profile": "startup",
        "company_size": "small",
        "generated_at": "2026-05-01",
        "period_start": "2026-04-01",
        "period_end": "2026-04-30",
        "priority_level": "critical" if priority_score >= 85 else "high" if priority_score >= 70 else "medium" if priority_score >= 45 else "low",
        "priority_score": priority_score,
    }


def _sample_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    index = 1
    templates = [
        {
            "rule_id": "ml_unusual_transaction",
            "severity": "critical",
            "category_name": "Marketing",
            "impact_amount": 95000.0,
            "impact_ratio": 0.92,
            "recurrence_count": 1.0,
            "confidence_score": 0.96,
            "flags": {"ml": 1, "fraud": 1, "expense": 1},
            "priority_score": 98.0,
        },
        {
            "rule_id": "critical_profit_drop",
            "severity": "critical",
            "category_name": "Professional Services",
            "impact_amount": 48000.0,
            "impact_ratio": 0.74,
            "recurrence_count": 2.0,
            "confidence_score": 0.93,
            "flags": {"profit": 1, "expense": 0},
            "priority_score": 96.0,
        },
        {
            "rule_id": "repeated_budget_overspending",
            "severity": "warning",
            "category_name": "Marketing",
            "impact_amount": 9500.0,
            "impact_ratio": 1.38,
            "recurrence_count": 5.0,
            "confidence_score": 0.88,
            "flags": {"budget": 1, "expense": 1},
            "priority_score": 82.0,
        },
        {
            "rule_id": "ml_spending_forecast_risk",
            "severity": "warning",
            "category_name": "Office Supplies",
            "impact_amount": 12000.0,
            "impact_ratio": 1.32,
            "recurrence_count": 2.0,
            "confidence_score": 0.84,
            "flags": {"ml": 1, "budget": 1, "forecast": 1, "expense": 1},
            "priority_score": 78.0,
        },
        {
            "rule_id": "ml_budget_recommendation",
            "severity": "info",
            "category_name": "Software",
            "impact_amount": 2800.0,
            "impact_ratio": 0.28,
            "recurrence_count": 1.0,
            "confidence_score": 0.72,
            "flags": {"ml": 1, "budget": 1, "expense": 1},
            "priority_score": 64.0,
        },
        {
            "rule_id": "expense_ratio",
            "severity": "info",
            "category_name": "Utilities",
            "impact_amount": 45.0,
            "impact_ratio": 0.06,
            "recurrence_count": 1.0,
            "confidence_score": 0.48,
            "flags": {"expense": 1},
            "priority_score": 36.0,
        },
    ]
    for _repeat in range(8):
        for template in templates:
            row = _row(index, **template)
            row["impact_amount"] = float(row["impact_amount"]) + (_repeat * 7.0)
            row["priority_score"] = min(100.0, float(row["priority_score"]) + (_repeat % 3))
            rows.append(row)
            index += 1
    return rows


def _write_dataset(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(_sample_rows())


def _trained_model(tmp_path: Path) -> tuple[Path, Path]:
    dataset_path = tmp_path / "insight_ranker.csv"
    model_path = tmp_path / "insight_ranker.joblib"
    _write_dataset(dataset_path)
    train(dataset_path=dataset_path, model_path=model_path, test_size=0.25)
    return dataset_path, model_path


def test_validation_script_runs(tmp_path: Path) -> None:
    dataset_path, model_path = _trained_model(tmp_path)

    result = validate_insight_ranker(model_path=model_path, dataset_path=dataset_path, test_size=0.25)

    assert result.dataset_rows > 0
    assert result.test_metrics["mae"] >= 0.0
    assert result.verdict in {"ready", "needs tuning", "failed"}


def test_high_risk_examples_score_above_medium_risk_examples(tmp_path: Path) -> None:
    _dataset_path, model_path = _trained_model(tmp_path)
    scenarios = {result.name: result for result in score_scenarios(load_artifact(model_path))}

    assert scenarios["Critical unusual transaction"].predicted_score > scenarios["Budget recommendation"].predicted_score
    assert scenarios["Critical profit drop"].predicted_score > scenarios["Forecast budget risk"].predicted_score


def test_low_info_example_does_not_outrank_critical_examples(tmp_path: Path) -> None:
    _dataset_path, model_path = _trained_model(tmp_path)
    scenarios = {result.name: result for result in score_scenarios(load_artifact(model_path))}

    low_info_score = scenarios["Small info insight"].predicted_score
    assert low_info_score < scenarios["Critical unusual transaction"].predicted_score
    assert low_info_score < scenarios["Critical profit drop"].predicted_score


def test_feature_mismatch_is_caught(tmp_path: Path) -> None:
    _dataset_path, model_path = _trained_model(tmp_path)
    artifact = load_artifact(model_path)
    artifact["metadata"]["feature_columns"] = [*artifact["metadata"]["feature_columns"], "priority_score"]
    mismatch_path = tmp_path / "mismatched_insight_ranker.joblib"
    joblib.dump(artifact, mismatch_path)

    with pytest.raises(RuntimeError, match="metadata feature_columns"):
        validate_artifact_contract(load_artifact(mismatch_path))


def test_model_family_is_correct(tmp_path: Path) -> None:
    _dataset_path, model_path = _trained_model(tmp_path)
    artifact = load_artifact(model_path)

    assert artifact["model_family"] == MODEL_FAMILY
