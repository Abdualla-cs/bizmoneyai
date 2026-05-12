from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor


DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "processed"
    / "bizmoneyai_insight_ranker.csv"
)
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "insight_ranker.joblib"

MODEL_NAME = "BizMoneyAI Model 5 Insight Importance Ranker"
MODEL_FAMILY = "bizmoneyai_insight_importance_ranker"
ALGORITHM = "XGBRegressor"
RANDOM_STATE = 42
TARGET_COLUMN = "priority_score"

FEATURE_COLUMNS = [
    "rule_id",
    "severity",
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
    "category_name",
]
CATEGORICAL_FEATURE_COLUMNS = [
    "rule_id",
    "severity",
    "category_name",
]
NUMERIC_FEATURE_COLUMNS = [
    column for column in FEATURE_COLUMNS if column not in CATEGORICAL_FEATURE_COLUMNS
]
OPTIONAL_UNSAFE_COLUMNS = [
    "business_profile",
    "company_size",
]
FORBIDDEN_FEATURE_COLUMNS = {
    TARGET_COLUMN,
    "priority_level",
    "insight_id",
    "title",
    "generated_at",
    "period_start",
    "period_end",
}
REQUIRED_COLUMNS = {TARGET_COLUMN, *FEATURE_COLUMNS}
TOP_K_VALUES = (10, 25, 50)


@dataclass(frozen=True)
class PreparedDataset:
    dataset_path: Path
    frame: pd.DataFrame
    source_rows: int
    feature_columns: list[str]
    categorical_columns: list[str]
    numeric_columns: list[str]
    excluded_columns: list[str]
    unsafe_optional_columns: list[str]


def _validate_required_columns(columns: list[str], dataset_path: Path) -> None:
    missing = sorted(REQUIRED_COLUMNS - set(columns))
    if missing:
        raise RuntimeError(f"{dataset_path} is missing required columns: {', '.join(missing)}")


def _validate_feature_policy() -> None:
    forbidden = sorted(set(FEATURE_COLUMNS) & FORBIDDEN_FEATURE_COLUMNS)
    if forbidden:
        raise RuntimeError(f"Model 5 feature policy forbids these columns: {', '.join(forbidden)}")
    if TARGET_COLUMN in FEATURE_COLUMNS:
        raise RuntimeError("Model 5 must not use priority_score as a feature")


def _coerce_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    series = pd.to_numeric(frame[column], errors="coerce")
    invalid_mask = series.isna()
    if invalid_mask.any():
        invalid_count = int(invalid_mask.sum())
        raise RuntimeError(f"Column '{column}' contains {invalid_count} invalid numeric values")
    return series.astype(float)


def prepare_training_data(dataset_path: Path = DEFAULT_DATASET_PATH) -> PreparedDataset:
    _validate_feature_policy()
    if not dataset_path.exists():
        raise RuntimeError(f"Insight ranker dataset not found at {dataset_path}")

    frame = pd.read_csv(dataset_path)
    columns = list(frame.columns)
    _validate_required_columns(columns, dataset_path)

    prepared = frame.loc[:, FEATURE_COLUMNS + [TARGET_COLUMN]].copy()
    for column in NUMERIC_FEATURE_COLUMNS + [TARGET_COLUMN]:
        prepared[column] = _coerce_numeric(prepared, column)

    for column in CATEGORICAL_FEATURE_COLUMNS:
        prepared[column] = (
            prepared[column]
            .fillna("unknown")
            .astype(str)
            .str.strip()
            .replace("", "unknown")
        )

    excluded_columns = sorted(column for column in columns if column not in FEATURE_COLUMNS and column != TARGET_COLUMN)
    unsafe_optional_columns = sorted(column for column in OPTIONAL_UNSAFE_COLUMNS if column in columns)

    return PreparedDataset(
        dataset_path=dataset_path,
        frame=prepared,
        source_rows=len(prepared),
        feature_columns=list(FEATURE_COLUMNS),
        categorical_columns=list(CATEGORICAL_FEATURE_COLUMNS),
        numeric_columns=list(NUMERIC_FEATURE_COLUMNS),
        excluded_columns=excluded_columns,
        unsafe_optional_columns=unsafe_optional_columns,
    )


def _model_pipeline(
    *,
    categorical_columns: list[str],
    numeric_columns: list[str],
) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            ),
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                    ]
                ),
                numeric_columns,
            ),
        ],
        remainder="drop",
    )
    model = XGBRegressor(
        objective="reg:squarederror",
        n_estimators=320,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_weight=3,
        reg_lambda=1.0,
        random_state=RANDOM_STATE,
        n_jobs=4,
    )
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true > 0
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])))


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "mape": round(_mape(y_true, y_pred), 4),
    }


def _top_k_overlap(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, dict[str, float | int]]:
    results: dict[str, dict[str, float | int]] = {}
    total_rows = len(y_true)
    if total_rows == 0:
        return results

    for requested_k in TOP_K_VALUES:
        k = min(requested_k, total_rows)
        if k <= 0:
            continue
        actual_top = set(np.argsort(y_true)[-k:])
        predicted_top = set(np.argsort(y_pred)[-k:])
        overlap = len(actual_top & predicted_top)
        results[f"top_{k}"] = {
            "k": k,
            "overlap_count": overlap,
            "overlap_ratio": round(overlap / k, 4),
        }
    return results


def _spearman_correlation(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float | None, str | None]:
    true_ranks = pd.Series(y_true).rank(method="average")
    pred_ranks = pd.Series(y_pred).rank(method="average")
    correlation = true_ranks.corr(pred_ranks, method="pearson")
    if correlation is None or pd.isna(correlation):
        return None, "Spearman correlation skipped because one side was constant after ranking."
    return round(float(correlation), 4), None


def _rank_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    spearman, note = _spearman_correlation(y_true, y_pred)
    metrics: dict[str, Any] = {
        "top_k_overlap": _top_k_overlap(y_true, y_pred),
    }
    if spearman is not None:
        metrics["spearman_correlation"] = spearman
    else:
        metrics["spearman_correlation"] = None
        metrics["spearman_note"] = note or "Spearman correlation was skipped."
    return metrics


def train(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    model_path: Path = DEFAULT_MODEL_PATH,
    *,
    test_size: float = 0.20,
) -> dict[str, Any]:
    prepared = prepare_training_data(dataset_path)
    features = prepared.frame.loc[:, prepared.feature_columns]
    target = prepared.frame[TARGET_COLUMN].astype(float)

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=test_size,
        random_state=RANDOM_STATE,
        shuffle=True,
    )

    pipeline = _model_pipeline(
        categorical_columns=prepared.categorical_columns,
        numeric_columns=prepared.numeric_columns,
    )
    pipeline.fit(x_train, y_train)

    train_predictions = pipeline.predict(x_train).astype(float)
    test_predictions = pipeline.predict(x_test).astype(float)
    y_train_values = y_train.to_numpy(dtype=float)
    y_test_values = y_test.to_numpy(dtype=float)

    training_metrics = _regression_metrics(y_train_values, train_predictions)
    validation_metrics = {
        **_regression_metrics(y_test_values, test_predictions),
        **_rank_metrics(y_test_values, test_predictions),
    }

    trained_at = datetime.now(timezone.utc).isoformat()
    artifact = {
        "model": pipeline,
        "preprocessor": pipeline.named_steps["preprocessor"],
        "feature_columns": list(prepared.feature_columns),
        "categorical_columns": list(prepared.categorical_columns),
        "numeric_columns": list(prepared.numeric_columns),
        "target_column": TARGET_COLUMN,
        "model_name": MODEL_NAME,
        "model_family": MODEL_FAMILY,
        "algorithm": ALGORITHM,
        "training_metrics": training_metrics,
        "validation_metrics": validation_metrics,
        "metadata": {
            "model_family": MODEL_FAMILY,
            "algorithm": ALGORITHM,
            "dataset_path": str(dataset_path),
            "source_rows": prepared.source_rows,
            "train_rows": len(x_train),
            "test_rows": len(x_test),
            "feature_columns": list(prepared.feature_columns),
            "categorical_columns": list(prepared.categorical_columns),
            "numeric_columns": list(prepared.numeric_columns),
            "excluded_columns": list(prepared.excluded_columns),
            "unsafe_optional_columns": list(prepared.unsafe_optional_columns),
            "training_metrics": training_metrics,
            "validation_metrics": validation_metrics,
            "trained_at": trained_at,
            "runtime_feature_policy": (
                "Training uses only fields that can be reproduced from runtime AIInsight rows "
                "or safe metadata. business_profile and company_size were intentionally excluded "
                "to avoid a train/serve mismatch."
            ),
        },
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)

    print(f"Dataset rows: {prepared.source_rows}")
    print(f"Train rows: {len(x_train)}")
    print(f"Test rows: {len(x_test)}")
    print(f"Feature columns: {', '.join(prepared.feature_columns)}")
    if prepared.unsafe_optional_columns:
        print(f"Excluded optional runtime-unsafe columns: {', '.join(prepared.unsafe_optional_columns)}")
    print(
        "Training metrics: "
        f"MAE={training_metrics['mae']:.4f}, "
        f"RMSE={training_metrics['rmse']:.4f}, "
        f"R2={training_metrics['r2']:.4f}, "
        f"MAPE={training_metrics['mape']:.4f}"
    )
    print(
        "Validation metrics: "
        f"MAE={validation_metrics['mae']:.4f}, "
        f"RMSE={validation_metrics['rmse']:.4f}, "
        f"R2={validation_metrics['r2']:.4f}, "
        f"MAPE={validation_metrics['mape']:.4f}"
    )
    if validation_metrics.get("spearman_correlation") is not None:
        print(f"Spearman correlation: {validation_metrics['spearman_correlation']:.4f}")
    else:
        print(validation_metrics.get("spearman_note", "Spearman correlation skipped."))
    print("Top-k overlap:")
    for key, summary in validation_metrics["top_k_overlap"].items():
        print(
            f"- {key}: overlap={summary['overlap_count']}/{summary['k']} "
            f"({summary['overlap_ratio']:.4f})"
        )
    print(f"Saved Model 5 insight ranker to {model_path}")

    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the BizMoneyAI Model 5 insight importance ranker.")
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--test-size", type=float, default=0.20)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(
        dataset_path=args.dataset_path,
        model_path=args.model_path,
        test_size=args.test_size,
    )
