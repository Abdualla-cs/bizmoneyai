from __future__ import annotations

import csv
from pathlib import Path

import joblib

from app.ml.insight_ranking.train_insight_ranker import (
    DEFAULT_DATASET_PATH,
    FEATURE_COLUMNS,
    MODEL_FAMILY,
    TARGET_COLUMN,
    prepare_training_data,
    train,
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


def _row(index: int) -> dict[str, object]:
    severity = "critical" if index % 4 == 0 else "warning"
    impact_amount = 200.0 + (index * 85.0)
    impact_ratio = 0.15 + (index * 0.03)
    confidence_score = 0.55 + ((index % 5) * 0.07)
    priority_score = 48.0 + (index * 2.4)
    return {
        "insight_id": index,
        "rule_id": "budget_overspend_ratio" if index % 2 == 0 else "spending_spike_percent",
        "title": f"Insight {index}",
        "severity": severity,
        "category_name": "Marketing" if index % 3 == 0 else "Software",
        "impact_amount": round(impact_amount, 2),
        "impact_ratio": round(impact_ratio, 4),
        "recurrence_count": (index % 4) + 1,
        "days_since_generated": index % 30,
        "period_days": 30 if index % 2 == 0 else 7,
        "confidence_score": round(min(confidence_score, 0.95), 4),
        "is_ml_generated": 1 if index % 5 == 0 else 0,
        "is_budget_related": 1 if index % 2 == 0 else 0,
        "is_fraud_related": 0,
        "is_forecast_related": 1 if index % 6 == 0 else 0,
        "is_income_related": 0,
        "is_profit_related": 0,
        "is_expense_related": 1,
        "business_profile": "startup",
        "company_size": "small",
        "generated_at": f"2026-05-{(index % 28) + 1:02d}",
        "period_start": "2026-04-01",
        "period_end": "2026-04-30",
        "priority_level": "critical" if priority_score >= 85 else "high" if priority_score >= 70 else "medium",
        "priority_score": round(min(priority_score, 96.0), 2),
    }


def _write_dataset(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def test_insight_ranker_training_dataset_exists() -> None:
    assert DEFAULT_DATASET_PATH.exists()


def test_training_script_can_load_dataset() -> None:
    prepared = prepare_training_data(DEFAULT_DATASET_PATH)

    assert prepared.source_rows > 0
    assert prepared.dataset_path == DEFAULT_DATASET_PATH
    assert TARGET_COLUMN in prepared.frame.columns


def test_target_is_not_used_as_a_feature() -> None:
    assert TARGET_COLUMN not in FEATURE_COLUMNS


def test_train_saves_artifact_with_required_metadata(tmp_path: Path) -> None:
    dataset_path = tmp_path / "insight_ranker.csv"
    model_path = tmp_path / "insight_ranker.joblib"
    _write_dataset(dataset_path, [_row(index) for index in range(1, 31)])

    train(dataset_path=dataset_path, model_path=model_path, test_size=0.25)

    assert model_path.exists()

    artifact = joblib.load(model_path)
    assert "model" in artifact
    assert "preprocessor" in artifact
    assert "feature_columns" in artifact
    assert "categorical_columns" in artifact
    assert "numeric_columns" in artifact
    assert "training_metrics" in artifact
    assert "validation_metrics" in artifact
    assert artifact["model_family"] == MODEL_FAMILY
    assert artifact["metadata"]["model_family"] == MODEL_FAMILY
    assert artifact["metadata"]["trained_at"]
    assert TARGET_COLUMN not in artifact["feature_columns"]


def test_artifact_contains_feature_metadata(tmp_path: Path) -> None:
    dataset_path = tmp_path / "insight_ranker.csv"
    model_path = tmp_path / "insight_ranker.joblib"
    _write_dataset(dataset_path, [_row(index) for index in range(1, 25)])

    artifact = train(dataset_path=dataset_path, model_path=model_path, test_size=0.25)

    assert artifact["categorical_columns"] == ["rule_id", "severity", "category_name"]
    assert "impact_amount" in artifact["numeric_columns"]
    assert "business_profile" not in artifact["feature_columns"]
    assert "company_size" not in artifact["feature_columns"]
    assert "top_k_overlap" in artifact["validation_metrics"]
