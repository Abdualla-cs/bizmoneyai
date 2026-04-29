from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal, TypedDict

import joblib
import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[1] / "ml" / "models" / "fraud_detector.joblib"
DEFAULT_MODEL_NAME = "BizMoneyAI Model 2 Fraud Detector"
WARNING_THRESHOLD = 0.50
CRITICAL_THRESHOLD = 0.80

RiskLevel = Literal["normal", "warning", "critical"]


class FraudPrediction(TypedDict):
    is_unusual: bool
    fraud_probability: float
    risk_level: RiskLevel
    model_name: str


class FraudDetector:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model_path = model_path
        self._model: Any | None = None
        self._feature_columns: list[str] = []
        self._threshold = WARNING_THRESHOLD
        self._model_name = DEFAULT_MODEL_NAME
        self._load_model()

    def _load_model(self) -> None:
        if not self.model_path.exists():
            logger.info("Fraud detector model not found at %s", self.model_path)
            return

        try:
            artifact = joblib.load(self.model_path)
        except Exception:
            logger.exception("Failed to load fraud detector model from %s", self.model_path)
            return

        if not isinstance(artifact, dict):
            logger.warning("Ignoring incompatible fraud detector artifact at %s", self.model_path)
            return

        model = artifact.get("model")
        feature_columns = artifact.get("feature_columns")
        metadata = artifact.get("metadata") or {}
        threshold = artifact.get("threshold", metadata.get("threshold", WARNING_THRESHOLD))

        if model is None or not hasattr(model, "predict_proba"):
            logger.warning("Ignoring fraud detector artifact without predict_proba model")
            return

        if (
            not isinstance(feature_columns, list)
            or not feature_columns
            or not all(isinstance(column, str) for column in feature_columns)
        ):
            logger.warning("Ignoring fraud detector artifact without feature column order")
            return

        try:
            self._threshold = float(threshold)
        except (TypeError, ValueError):
            self._threshold = WARNING_THRESHOLD

        if isinstance(metadata, dict):
            self._model_name = str(metadata.get("model_name") or DEFAULT_MODEL_NAME)

        self._model = model
        self._feature_columns = feature_columns
        logger.info("Fraud detector loaded from %s", self.model_path)

    def is_ready(self) -> bool:
        return self._model is not None and bool(self._feature_columns)

    def _normal_response(self) -> FraudPrediction:
        return {
            "is_unusual": False,
            "fraud_probability": 0.0,
            "risk_level": "normal",
            "model_name": self._model_name,
        }

    def _safe_float(self, payload: dict[str, Any], key: str, default: float = 0.0) -> float:
        value = payload.get(key, default)
        if value in (None, ""):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _transaction_type(self, payload: dict[str, Any]) -> str:
        raw_value = payload.get("type", "")
        if raw_value in (None, ""):
            return ""
        return str(raw_value).strip().upper().replace("-", "_").replace(" ", "_")

    def _engineered_features(self, payload: dict[str, Any]) -> dict[str, float]:
        amount = self._safe_float(payload, "amount")
        step = self._safe_float(payload, "step")
        oldbalance_org = self._safe_float(payload, "oldbalanceOrg")
        newbalance_orig = self._safe_float(payload, "newbalanceOrig")
        oldbalance_dest = self._safe_float(payload, "oldbalanceDest")
        newbalance_dest = self._safe_float(payload, "newbalanceDest")

        return {
            "amount": amount,
            "step": step,
            "oldbalanceOrg": oldbalance_org,
            "newbalanceOrig": newbalance_orig,
            "oldbalanceDest": oldbalance_dest,
            "newbalanceDest": newbalance_dest,
            "orig_balance_delta": self._safe_float(
                payload,
                "orig_balance_delta",
                oldbalance_org - newbalance_orig,
            ),
            "dest_balance_delta": self._safe_float(
                payload,
                "dest_balance_delta",
                newbalance_dest - oldbalance_dest,
            ),
            "orig_error": self._safe_float(
                payload,
                "orig_error",
                oldbalance_org - amount - newbalance_orig,
            ),
            "dest_error": self._safe_float(
                payload,
                "dest_error",
                oldbalance_dest + amount - newbalance_dest,
            ),
        }

    def _build_feature_row(self, payload: dict[str, Any]) -> np.ndarray:
        engineered = self._engineered_features(payload)
        transaction_type = self._transaction_type(payload)
        values: list[float] = []

        for column in self._feature_columns:
            if column in engineered:
                values.append(engineered[column])
            elif column.startswith("type_"):
                explicit_value = payload.get(column)
                if explicit_value not in (None, ""):
                    values.append(self._safe_float(payload, column))
                else:
                    values.append(1.0 if transaction_type == column.removeprefix("type_") else 0.0)
            else:
                values.append(self._safe_float(payload, column))

        return np.array([values], dtype=np.float32)

    def _fraud_probability(self, feature_row: np.ndarray) -> float:
        if self._model is None:
            return 0.0

        probabilities = self._model.predict_proba(feature_row)
        classes = getattr(self._model, "classes_", None)
        fraud_index = 1

        if classes is not None:
            class_values = [str(class_value) for class_value in classes]
            if "1" in class_values:
                fraud_index = class_values.index("1")

        probability = float(probabilities[0][fraud_index])
        return max(0.0, min(1.0, probability))

    def _risk_level(self, probability: float) -> RiskLevel:
        if probability >= CRITICAL_THRESHOLD:
            return "critical"
        if probability >= WARNING_THRESHOLD:
            return "warning"
        return "normal"

    def predict(self, payload: dict[str, Any]) -> FraudPrediction:
        if not self.is_ready():
            return self._normal_response()

        try:
            feature_row = self._build_feature_row(payload)
            fraud_probability = self._fraud_probability(feature_row)
            risk_level = self._risk_level(fraud_probability)
            return {
                "is_unusual": risk_level != "normal",
                "fraud_probability": round(fraud_probability, 6),
                "risk_level": risk_level,
                "model_name": self._model_name,
            }
        except Exception:
            logger.exception("Fraud detector prediction failed")
            return self._normal_response()


detector = FraudDetector()


def is_ready() -> bool:
    return detector.is_ready()


def predict(payload: dict[str, Any]) -> FraudPrediction:
    return detector.predict(payload)
