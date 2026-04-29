from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split


DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "processed"
    / "paysim_fraud_processed.csv"
)
DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[1] / "models" / "fraud_detector.joblib"
)

TARGET_COLUMN = "isFraud"
DEFAULT_THRESHOLD = 0.5
RANDOM_STATE = 42
TEST_SIZE = 0.2


def _read_columns(dataset_path: Path) -> list[str]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Processed PaySim dataset not found at {dataset_path}")

    with dataset_path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            columns = next(reader)
        except StopIteration as exc:
            raise ValueError(f"Processed dataset is empty: {dataset_path}") from exc

    if TARGET_COLUMN not in columns:
        raise ValueError(f"Processed dataset must include target column {TARGET_COLUMN!r}")

    feature_columns = [column for column in columns if column != TARGET_COLUMN]
    if not feature_columns:
        raise ValueError("Processed dataset must include at least one feature column")

    return columns


def _load_dataset(dataset_path: Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    columns = _read_columns(dataset_path)
    target_index = columns.index(TARGET_COLUMN)
    feature_indices = [index for index, column in enumerate(columns) if column != TARGET_COLUMN]
    feature_columns = [columns[index] for index in feature_indices]

    print(f"Loading processed dataset from {dataset_path}")
    x = np.loadtxt(
        dataset_path,
        delimiter=",",
        skiprows=1,
        usecols=feature_indices,
        dtype=np.float32,
    )
    y = np.loadtxt(
        dataset_path,
        delimiter=",",
        skiprows=1,
        usecols=target_index,
        dtype=np.int8,
    )

    if x.ndim == 1:
        x = x.reshape(1, -1)
    y = np.atleast_1d(y).astype(np.int8, copy=False)

    unique_targets = set(np.unique(y).tolist())
    if not unique_targets.issubset({0, 1}):
        raise ValueError(
            f"{TARGET_COLUMN!r} must contain binary labels 0/1. "
            f"Found: {sorted(unique_targets)}"
        )

    return x, y, feature_columns


def _target_distribution(y: np.ndarray) -> dict[str, int]:
    values, counts = np.unique(y, return_counts=True)
    return {str(int(value)): int(count) for value, count in zip(values, counts)}


def _validate_threshold(threshold: float) -> None:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("Classification threshold must be between 0.0 and 1.0")


def _evaluate_model(
    model: RandomForestClassifier,
    x_test: np.ndarray,
    y_test: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    if hasattr(model, "predict_proba"):
        fraud_probabilities = model.predict_proba(x_test)[:, 1]
        predictions = (fraud_probabilities >= threshold).astype(np.int8)
        roc_auc = roc_auc_score(y_test, fraud_probabilities)
    else:
        fraud_probabilities = None
        predictions = model.predict(x_test)
        roc_auc = None

    matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
    return {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1_score": float(f1_score(y_test, predictions, zero_division=0)),
        "confusion_matrix": matrix.tolist(),
        "roc_auc": None if roc_auc is None else float(roc_auc),
        "threshold": threshold,
        "used_predict_proba": fraud_probabilities is not None,
    }


def _print_metrics(metrics: dict[str, Any]) -> None:
    print("Evaluation metrics:")
    print(f"- accuracy: {metrics['accuracy']:.6f}")
    print(f"- precision: {metrics['precision']:.6f}")
    print(f"- recall: {metrics['recall']:.6f}")
    print(f"- f1-score: {metrics['f1_score']:.6f}")
    print(f"- confusion matrix [[tn, fp], [fn, tp]]: {metrics['confusion_matrix']}")
    if metrics["roc_auc"] is None:
        print("- ROC-AUC: n/a")
    else:
        print(f"- ROC-AUC: {metrics['roc_auc']:.6f}")

    print(
        "Imbalance note: accuracy alone is not enough for fraud detection. "
        "Recall shows how many fraud cases are caught, while precision shows "
        "how many flagged transactions are truly fraud."
    )


def train(dataset_path: Path, model_path: Path, threshold: float) -> dict[str, Any]:
    _validate_threshold(threshold)

    x, y, feature_columns = _load_dataset(dataset_path)
    print(f"Dataset shape: {x.shape[0]} rows, {x.shape[1]} features")
    print(f"Feature columns: {', '.join(feature_columns)}")
    print(f"Target distribution: {_target_distribution(y)}")

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=None,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    print("Training RandomForestClassifier...")
    model.fit(x_train, y_train)

    metrics = _evaluate_model(model, x_test, y_test, threshold)
    _print_metrics(metrics)

    metadata = {
        "model_name": "BizMoneyAI Model 2 Fraud Detector",
        "model_type": "RandomForestClassifier",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "target_column": TARGET_COLUMN,
        "feature_columns": feature_columns,
        "threshold": threshold,
        "random_state": RANDOM_STATE,
        "test_size": TEST_SIZE,
        "sklearn_version": sklearn.__version__,
        "parameters": {
            "n_estimators": 100,
            "max_depth": None,
            "class_weight": "balanced",
            "random_state": RANDOM_STATE,
            "n_jobs": -1,
        },
        "class_imbalance_handling": [
            "RandomForestClassifier uses class_weight='balanced'.",
            "Train/test split uses stratify=y to preserve fraud ratio.",
        ],
        "train_rows": int(x_train.shape[0]),
        "test_rows": int(x_test.shape[0]),
        "target_distribution": {
            "all": _target_distribution(y),
            "train": _target_distribution(y_train),
            "test": _target_distribution(y_test),
        },
        "metrics": metrics,
        "limitations": [
            "PaySim is synthetic and may not match production transaction behavior.",
            "The fraud class is highly imbalanced, so accuracy must not be used alone.",
            "The default threshold is 0.5 and should be reviewed against product risk tolerance.",
        ],
    }

    artifact = {
        "model": model,
        "feature_columns": feature_columns,
        "threshold": threshold,
        "metadata": metadata,
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)
    print(f"Saved fraud detector artifact to {model_path}")
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the supervised PaySim fraud detection model."
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the processed PaySim CSV file.",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Path where the trained model artifact should be saved.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="Fraud probability threshold used for risk classification.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args.dataset_path, args.model_path, args.threshold)
