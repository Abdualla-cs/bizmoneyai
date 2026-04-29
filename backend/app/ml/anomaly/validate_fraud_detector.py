from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split

from app.services.fraud_detector import FraudDetector


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
DEFAULT_RANDOM_STATE = 42
DEFAULT_TEST_SIZE = 0.2


@dataclass(frozen=True)
class MetricResult:
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float | None
    confusion_matrix: list[list[int]]
    false_positives: int
    false_negatives: int


def _read_columns(dataset_path: Path) -> list[str]:
    with dataset_path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            return next(reader)
        except StopIteration as exc:
            raise ValueError(f"Processed dataset is empty: {dataset_path}") from exc


def _feature_columns_from_dataset(dataset_path: Path) -> list[str]:
    columns = _read_columns(dataset_path)
    if TARGET_COLUMN not in columns:
        raise ValueError(f"Processed dataset is missing {TARGET_COLUMN!r}")
    return [column for column in columns if column != TARGET_COLUMN]


def _load_processed_dataset(dataset_path: Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    columns = _read_columns(dataset_path)
    if TARGET_COLUMN not in columns:
        raise ValueError(f"Processed dataset is missing {TARGET_COLUMN!r}")

    target_index = columns.index(TARGET_COLUMN)
    feature_indices = [index for index, column in enumerate(columns) if column != TARGET_COLUMN]
    feature_columns = [columns[index] for index in feature_indices]

    print(f"Loading processed dataset: {dataset_path}")
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
    return x, y, feature_columns


def _load_artifact(model_path: Path) -> dict[str, Any]:
    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact not found: {model_path}")
    artifact = joblib.load(model_path)
    if not isinstance(artifact, dict):
        raise TypeError("Model artifact is not a dictionary")
    return artifact


def inspect_artifact(model_path: Path, dataset_path: Path) -> dict[str, Any]:
    artifact = _load_artifact(model_path)
    model = artifact.get("model")
    feature_columns = artifact.get("feature_columns")
    metadata = artifact.get("metadata")
    threshold = artifact.get("threshold")
    dataset_feature_columns = _feature_columns_from_dataset(dataset_path)

    print("Artifact inspection:")
    print(f"- path: {model_path}")
    print(f"- contains model: {model is not None}")
    print(f"- model type: {type(model).__name__ if model is not None else 'missing'}")
    print(f"- has predict_proba: {hasattr(model, 'predict_proba')}")
    print(f"- contains feature column order: {isinstance(feature_columns, list) and bool(feature_columns)}")
    print(f"- feature columns match processed data: {feature_columns == dataset_feature_columns}")
    print(f"- contains threshold: {threshold is not None}")
    print(f"- threshold: {threshold}")
    print(f"- contains metadata: {isinstance(metadata, dict)}")
    if isinstance(metadata, dict):
        print(f"- model name: {metadata.get('model_name')}")
        print(f"- model type metadata: {metadata.get('model_type')}")
        print(f"- trained at: {metadata.get('trained_at')}")
        print(f"- sklearn version: {metadata.get('sklearn_version')}")
        print(f"- saved metrics: {metadata.get('metrics')}")
    print("- runtime risk settings: warning >= 0.50, critical >= 0.80")
    return artifact


def _metrics_from_predictions(
    y_true: np.ndarray,
    predictions: np.ndarray,
    probabilities: np.ndarray | None,
) -> MetricResult:
    matrix = confusion_matrix(y_true, predictions, labels=[0, 1])
    roc_auc = None
    if probabilities is not None and len(np.unique(y_true)) == 2:
        roc_auc = float(roc_auc_score(y_true, probabilities))

    return MetricResult(
        accuracy=float(accuracy_score(y_true, predictions)),
        precision=float(precision_score(y_true, predictions, zero_division=0)),
        recall=float(recall_score(y_true, predictions, zero_division=0)),
        f1_score=float(f1_score(y_true, predictions, zero_division=0)),
        roc_auc=roc_auc,
        confusion_matrix=matrix.tolist(),
        false_positives=int(matrix[0][1]),
        false_negatives=int(matrix[1][0]),
    )


def _predict_probabilities(
    model: Any,
    x: np.ndarray,
    batch_size: int,
    indices: np.ndarray | None = None,
) -> np.ndarray:
    row_count = x.shape[0] if indices is None else indices.shape[0]
    probabilities = np.empty(row_count, dtype=np.float32)
    for start in range(0, row_count, batch_size):
        end = min(start + batch_size, row_count)
        batch = x[start:end] if indices is None else x[indices[start:end]]
        probabilities[start:end] = model.predict_proba(batch)[:, 1]
    return probabilities


def _print_metric_result(label: str, metrics: MetricResult) -> None:
    print(f"{label}:")
    print(f"- accuracy: {metrics.accuracy:.6f}")
    print(f"- precision: {metrics.precision:.6f}")
    print(f"- recall: {metrics.recall:.6f}")
    print(f"- f1-score: {metrics.f1_score:.6f}")
    print(f"- ROC-AUC: {'n/a' if metrics.roc_auc is None else f'{metrics.roc_auc:.6f}'}")
    print(f"- confusion matrix [[tn, fp], [fn, tp]]: {metrics.confusion_matrix}")
    print(f"- false positives: {metrics.false_positives}")
    print(f"- false negatives: {metrics.false_negatives}")


def evaluate_holdout(
    artifact: dict[str, Any],
    dataset_path: Path,
    batch_size: int,
) -> tuple[MetricResult, MetricResult]:
    model = artifact.get("model")
    if model is None or not hasattr(model, "predict_proba"):
        raise ValueError("Artifact does not contain a predict_proba model")

    metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    threshold = float(artifact.get("threshold", metadata.get("threshold", DEFAULT_THRESHOLD)))
    random_state = int(metadata.get("random_state", DEFAULT_RANDOM_STATE))
    test_size = float(metadata.get("test_size", DEFAULT_TEST_SIZE))

    x, y, _feature_columns = _load_processed_dataset(dataset_path)
    indices = np.arange(y.shape[0])
    train_indices, test_indices = train_test_split(
        indices,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    print(f"Holdout split: train={len(train_indices)}, test={len(test_indices)}, threshold={threshold}")

    test_probabilities = _predict_probabilities(model, x, batch_size, test_indices)
    test_predictions = (test_probabilities >= threshold).astype(np.int8)
    test_metrics = _metrics_from_predictions(y[test_indices], test_predictions, test_probabilities)
    _print_metric_result("Test metrics", test_metrics)

    train_probabilities = _predict_probabilities(model, x, batch_size, train_indices)
    train_predictions = (train_probabilities >= threshold).astype(np.int8)
    train_metrics = _metrics_from_predictions(y[train_indices], train_predictions, train_probabilities)
    _print_metric_result("Train metrics", train_metrics)

    print("Train/test gap:")
    print(f"- accuracy gap: {train_metrics.accuracy - test_metrics.accuracy:.6f}")
    print(f"- precision gap: {train_metrics.precision - test_metrics.precision:.6f}")
    print(f"- recall gap: {train_metrics.recall - test_metrics.recall:.6f}")
    print(f"- f1 gap: {train_metrics.f1_score - test_metrics.f1_score:.6f}")
    if train_metrics.roc_auc is not None and test_metrics.roc_auc is not None:
        print(f"- ROC-AUC gap: {train_metrics.roc_auc - test_metrics.roc_auc:.6f}")
    return train_metrics, test_metrics


def evaluate_sampled_cross_validation(
    dataset_path: Path,
    *,
    normal_rows: int,
    folds: int,
    random_state: int,
) -> list[MetricResult]:
    x, y, feature_columns = _load_processed_dataset(dataset_path)
    rng = np.random.default_rng(random_state)
    fraud_indices = np.flatnonzero(y == 1)
    normal_indices = np.flatnonzero(y == 0)
    normal_sample_size = min(normal_rows, len(normal_indices))
    sampled_normal_indices = rng.choice(normal_indices, size=normal_sample_size, replace=False)
    sample_indices = np.concatenate([fraud_indices, sampled_normal_indices])
    rng.shuffle(sample_indices)

    x_sample = x[sample_indices]
    y_sample = y[sample_indices]
    print(
        "Sampled CV dataset: "
        f"rows={len(sample_indices)}, fraud={int((y_sample == 1).sum())}, "
        f"normal={int((y_sample == 0).sum())}, features={len(feature_columns)}"
    )

    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=random_state)
    fold_metrics: list[MetricResult] = []
    for fold_number, (train_index, test_index) in enumerate(cv.split(x_sample, y_sample), start=1):
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=None,
            class_weight="balanced",
            random_state=random_state,
            n_jobs=-1,
        )
        model.fit(x_sample[train_index], y_sample[train_index])
        probabilities = model.predict_proba(x_sample[test_index])[:, 1]
        predictions = (probabilities >= DEFAULT_THRESHOLD).astype(np.int8)
        metrics = _metrics_from_predictions(y_sample[test_index], predictions, probabilities)
        fold_metrics.append(metrics)
        _print_metric_result(f"CV fold {fold_number}", metrics)

    precision_values = np.array([metrics.precision for metrics in fold_metrics])
    recall_values = np.array([metrics.recall for metrics in fold_metrics])
    f1_values = np.array([metrics.f1_score for metrics in fold_metrics])
    print("Sampled CV summary:")
    print(f"- mean precision: {precision_values.mean():.6f}")
    print(f"- precision variance: {precision_values.var():.8f}")
    print(f"- mean recall: {recall_values.mean():.6f}")
    print(f"- recall variance: {recall_values.var():.8f}")
    print(f"- mean f1: {f1_values.mean():.6f}")
    print(f"- f1 variance: {f1_values.var():.8f}")
    return fold_metrics


def run_runtime_examples(model_path: Path) -> None:
    detector = FraudDetector(model_path=model_path)
    cases = [
        (
            "normal small PAYMENT",
            {
                "amount": 25.0,
                "type": "PAYMENT",
                "step": 10,
                "oldbalanceOrg": 1000.0,
                "newbalanceOrig": 975.0,
                "oldbalanceDest": 0.0,
                "newbalanceDest": 0.0,
            },
        ),
        (
            "normal moderate CASH_OUT",
            {
                "amount": 250.0,
                "type": "CASH_OUT",
                "step": 12,
                "oldbalanceOrg": 1000.0,
                "newbalanceOrig": 750.0,
                "oldbalanceDest": 2000.0,
                "newbalanceDest": 2250.0,
            },
        ),
        (
            "normal CASH_IN",
            {
                "amount": 500.0,
                "type": "CASH_IN",
                "step": 14,
                "oldbalanceOrg": 500.0,
                "newbalanceOrig": 1000.0,
                "oldbalanceDest": 0.0,
                "newbalanceDest": 0.0,
            },
        ),
        (
            "suspicious very large TRANSFER",
            {
                "amount": 10_000_000.0,
                "type": "TRANSFER",
                "step": 20,
                "oldbalanceOrg": 10_000_000.0,
                "newbalanceOrig": 0.0,
                "oldbalanceDest": 0.0,
                "newbalanceDest": 0.0,
            },
        ),
        (
            "suspicious balance mismatch",
            {
                "amount": 5000.0,
                "type": "CASH_OUT",
                "step": 22,
                "oldbalanceOrg": 1000.0,
                "newbalanceOrig": 1000.0,
                "oldbalanceDest": 0.0,
                "newbalanceDest": 0.0,
            },
        ),
        (
            "suspicious origin unchanged after transfer",
            {
                "amount": 10_000.0,
                "type": "TRANSFER",
                "step": 25,
                "oldbalanceOrg": 25_000.0,
                "newbalanceOrig": 25_000.0,
                "oldbalanceDest": 0.0,
                "newbalanceDest": 0.0,
            },
        ),
        (
            "suspicious extreme amount",
            {
                "amount": 100_000_000.0,
                "type": "TRANSFER",
                "step": 30,
                "oldbalanceOrg": 100_000_000.0,
                "newbalanceOrig": 0.0,
                "oldbalanceDest": 0.0,
                "newbalanceDest": 0.0,
            },
        ),
    ]

    print("Runtime prediction examples:")
    print(f"- detector ready: {detector.is_ready()}")
    for name, payload in cases:
        result = detector.predict(payload)
        print(
            f"- {name}: probability={result['fraud_probability']:.6f}, "
            f"risk_level={result['risk_level']}, is_unusual={result['is_unusual']}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the BizMoneyAI Model 2 fraud detector artifact."
    )
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--full-eval", action="store_true", help="Run train/test holdout evaluation.")
    parser.add_argument("--cv", action="store_true", help="Run sampled 3-fold cross-validation.")
    parser.add_argument("--cv-normal-rows", type=int, default=50_000)
    parser.add_argument("--cv-folds", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=250_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact = inspect_artifact(args.model_path, args.dataset_path)
    run_runtime_examples(args.model_path)
    if args.full_eval:
        evaluate_holdout(artifact, args.dataset_path, args.batch_size)
    if args.cv:
        evaluate_sampled_cross_validation(
            args.dataset_path,
            normal_rows=args.cv_normal_rows,
            folds=args.cv_folds,
            random_state=DEFAULT_RANDOM_STATE,
        )


if __name__ == "__main__":
    main()
