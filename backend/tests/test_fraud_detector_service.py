from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pytest

from app.services.fraud_detector import FEATURE_COLUMNS, MODEL_FAMILY, FraudDetector


class FakeAnomalyModel:
    def __init__(self, raw_anomaly_score: float) -> None:
        self.raw_anomaly_score = raw_anomaly_score

    def decision_function(self, rows):
        return np.full(len(rows), -self.raw_anomaly_score, dtype=np.float32)


def _write_fake_artifact(tmp_path: Path, raw_anomaly_score: float) -> Path:
    model_path = tmp_path / "fraud_detector.joblib"
    joblib.dump(
        {
            "model": FakeAnomalyModel(raw_anomaly_score),
            "feature_columns": FEATURE_COLUMNS,
            "model_family": MODEL_FAMILY,
            "risk_thresholds": {
                "warning_raw": 0.02,
                "critical_raw": 0.08,
                "raw_score_floor": -0.20,
            },
            "metadata": {
                "model_name": "Fake BizMoneyAI Anomaly Detector",
                "model_family": MODEL_FAMILY,
            },
        },
        model_path,
    )
    return model_path


def _assert_prediction_schema(result):
    assert set(result.keys()) == {
        "is_unusual",
        "fraud_probability",
        "risk_level",
        "model_name",
    }
    assert isinstance(result["is_unusual"], bool)
    assert isinstance(result["fraud_probability"], float)
    assert result["risk_level"] in {"normal", "warning", "critical"}
    assert isinstance(result["model_name"], str)


def test_missing_model_does_not_crash(tmp_path):
    detector = FraudDetector(model_path=tmp_path / "missing-fraud-detector.joblib")

    assert detector.is_ready() is False
    result = detector.predict({"amount": 1000000, "type": "expense"})

    _assert_prediction_schema(result)
    assert result["is_unusual"] is False
    assert result["fraud_probability"] == 0.0
    assert result["risk_level"] == "normal"


def test_normal_transaction_returns_normal(tmp_path):
    detector = FraudDetector(model_path=_write_fake_artifact(tmp_path, -0.10))

    result = detector.predict(
        {
            "amount": 125,
            "type": "expense",
            "category_name": "Office Supplies",
            "description": "Office purchase",
            "date": "2026-04-10",
            "budget_amount": 1500,
            "budget_spent_before": 300,
            "user_avg_amount": 450,
            "category_avg_amount": 240,
            "recent_transaction_count": 12,
        }
    )

    _assert_prediction_schema(result)
    assert result["is_unusual"] is False
    assert result["risk_level"] == "normal"
    assert result["model_name"] == "Fake BizMoneyAI Anomaly Detector"


def test_normal_income_is_not_flagged_by_model_only_warning(tmp_path):
    detector = FraudDetector(model_path=_write_fake_artifact(tmp_path, 0.03))

    result = detector.predict(
        {
            "amount": 10000,
            "type": "income",
            "category_name": "Sales",
            "description": "Client invoice payment",
            "date": "2026-04-10",
            "budget_amount": 0,
            "budget_spent_before": 0,
            "user_avg_amount": 5000,
            "category_avg_amount": 5000,
            "recent_transaction_count": 8,
        }
    )

    _assert_prediction_schema(result)
    assert result["is_unusual"] is False
    assert result["fraud_probability"] < 0.5
    assert result["risk_level"] == "normal"


def test_moderate_software_overspend_is_not_flagged_by_model_only_warning(tmp_path):
    detector = FraudDetector(model_path=_write_fake_artifact(tmp_path, 0.03))

    result = detector.predict(
        {
            "amount": 2300,
            "type": "expense",
            "category_name": "Software",
            "description": "Team subscription renewal",
            "date": "2026-04-12",
            "budget_amount": 1500,
            "budget_spent_before": 0,
            "user_avg_amount": 1500,
            "category_avg_amount": 1500,
            "recent_transaction_count": 8,
        }
    )

    _assert_prediction_schema(result)
    assert result["is_unusual"] is False
    assert result["fraud_probability"] < 0.5
    assert result["risk_level"] == "normal"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "amount": 45000,
            "type": "expense",
            "category_name": "Marketing",
            "description": "Emergency vendor transfer for urgent campaign settlement",
            "date": "2026-04-25",
            "budget_amount": 4000,
            "budget_spent_before": 3999,
            "user_avg_amount": 1200,
            "category_avg_amount": 1100,
            "recent_transaction_count": 1,
        },
        {
            "amount": 85000,
            "type": "expense",
            "category_name": "Consulting",
            "description": "Urgent offshore contractor transfer",
            "date": "2026-04-27",
            "budget_amount": 9000,
            "budget_spent_before": 0,
            "user_avg_amount": 2000,
            "category_avg_amount": 1800,
            "recent_transaction_count": 1,
        },
    ],
)
def test_huge_budget_overspend_returns_critical(tmp_path, payload):
    detector = FraudDetector(model_path=_write_fake_artifact(tmp_path, 0.03))

    result = detector.predict(payload)

    _assert_prediction_schema(result)
    assert result["is_unusual"] is True
    assert result["fraud_probability"] >= 0.8
    assert result["risk_level"] == "critical"


def test_strong_software_overspend_returns_warning_or_critical(tmp_path):
    detector = FraudDetector(model_path=_write_fake_artifact(tmp_path, -0.10))

    result = detector.predict(
        {
            "amount": 16000,
            "type": "expense",
            "category_name": "Software",
            "description": "Manual override wire payment for immediate supplier settlement",
            "date": "2026-04-26",
            "budget_amount": 4500,
            "budget_spent_before": 900,
            "user_avg_amount": 900,
            "category_avg_amount": 850,
            "recent_transaction_count": 8,
        }
    )

    _assert_prediction_schema(result)
    assert result["is_unusual"] is True
    assert result["risk_level"] in {"warning", "critical"}


def test_suspicious_urgent_transfer_triggers_warning_or_critical(tmp_path):
    detector = FraudDetector(model_path=_write_fake_artifact(tmp_path, -0.10))

    result = detector.predict(
        {
            "amount": 7000,
            "type": "expense",
            "category_name": "Software",
            "description": "Urgent wire transfer for vendor settlement",
            "date": "2026-04-26",
            "budget_amount": 6000,
            "budget_spent_before": 500,
            "user_avg_amount": 900,
            "category_avg_amount": 850,
            "recent_transaction_count": 8,
        }
    )

    _assert_prediction_schema(result)
    assert result["is_unusual"] is True
    assert result["risk_level"] in {"warning", "critical"}
