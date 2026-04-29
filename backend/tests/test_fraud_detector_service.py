from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np

from app.services.fraud_detector import FraudDetector


FEATURE_COLUMNS = [
    "amount",
    "step",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
    "orig_balance_delta",
    "dest_balance_delta",
    "orig_error",
    "dest_error",
    "type_PAYMENT",
    "type_TRANSFER",
]


class FakeFraudModel:
    classes_ = np.array([0, 1])

    def __init__(self, fraud_probability: float) -> None:
        self.fraud_probability = fraud_probability

    def predict_proba(self, rows):
        return np.vstack(
            [
                np.array([1.0 - self.fraud_probability, self.fraud_probability])
                for _row in rows
            ]
        )


def _write_fake_artifact(tmp_path: Path, fraud_probability: float) -> Path:
    model_path = tmp_path / "fraud_detector.joblib"
    joblib.dump(
        {
            "model": FakeFraudModel(fraud_probability),
            "feature_columns": FEATURE_COLUMNS,
            "threshold": 0.5,
            "metadata": {"model_name": "Fake Fraud Detector"},
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
    result = detector.predict({"amount": 1000000, "type": "TRANSFER"})

    _assert_prediction_schema(result)
    assert result["is_unusual"] is False
    assert result["fraud_probability"] == 0.0
    assert result["risk_level"] == "normal"


def test_valid_input_returns_expected_schema(tmp_path):
    detector = FraudDetector(model_path=_write_fake_artifact(tmp_path, 0.72))

    result = detector.predict(
        {
            "amount": 2500,
            "step": 12,
            "oldbalanceOrg": 5000,
            "newbalanceOrig": 2500,
            "oldbalanceDest": 1000,
            "newbalanceDest": 3500,
            "type": "PAYMENT",
        }
    )

    _assert_prediction_schema(result)
    assert result == {
        "is_unusual": True,
        "fraud_probability": 0.72,
        "risk_level": "warning",
        "model_name": "Fake Fraud Detector",
    }


def test_extreme_amount_returns_valid_output(tmp_path):
    detector = FraudDetector(model_path=_write_fake_artifact(tmp_path, 0.93))

    result = detector.predict(
        {
            "amount": 999999999999,
            "step": 999,
            "oldbalanceOrg": 999999999999,
            "newbalanceOrig": 0,
            "oldbalanceDest": 0,
            "newbalanceDest": 999999999999,
            "type": "UNKNOWN_TRANSFER_TYPE",
        }
    )

    _assert_prediction_schema(result)
    assert result["is_unusual"] is True
    assert result["fraud_probability"] == 0.93
    assert result["risk_level"] == "critical"
