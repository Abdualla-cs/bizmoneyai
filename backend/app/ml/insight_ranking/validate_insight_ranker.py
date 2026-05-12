from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from app.ml.insight_ranking.train_insight_ranker import (
    CATEGORICAL_FEATURE_COLUMNS,
    DEFAULT_DATASET_PATH,
    DEFAULT_MODEL_PATH,
    FEATURE_COLUMNS,
    FORBIDDEN_FEATURE_COLUMNS,
    MODEL_FAMILY,
    NUMERIC_FEATURE_COLUMNS,
    RANDOM_STATE,
    TARGET_COLUMN,
    prepare_training_data,
)


EXPECTED_MODEL_FAMILY = "bizmoneyai_insight_importance_ranker"
REQUIRED_ARTIFACT_KEYS = {
    "model",
    "feature_columns",
    "categorical_columns",
    "numeric_columns",
    "target_column",
    "model_family",
    "metadata",
}
TOP_K_VALUES = (10, 20)
Verdict = Literal["ready", "needs tuning", "failed"]


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    expected_behavior: str
    predicted_score: float
    predicted_level: str
    features: dict[str, float | str]


@dataclass(frozen=True)
class ValidationResult:
    model_path: Path
    dataset_path: Path
    dataset_rows: int
    train_rows: int
    test_rows: int
    feature_columns: list[str]
    categorical_columns: list[str]
    numeric_columns: list[str]
    train_metrics: dict[str, float]
    test_metrics: dict[str, float]
    train_test_gap: dict[str, float]
    ranking_metrics: dict[str, Any]
    scenario_results: list[ScenarioResult]
    warnings: list[str]
    verdict: Verdict


def _priority_level(score: float) -> str:
    if score >= 85.0:
        return "critical"
    if score >= 70.0:
        return "high"
    if score >= 45.0:
        return "medium"
    return "low"


def _clamp_score(value: Any) -> float:
    score = float(value)
    if math.isnan(score) or math.isinf(score):
        raise ValueError(f"Invalid predicted priority score: {value!r}")
    return round(min(max(score, 0.0), 100.0), 4)


def load_artifact(model_path: Path = DEFAULT_MODEL_PATH) -> dict[str, Any]:
    if not model_path.exists():
        raise RuntimeError(f"Model 5 artifact not found at {model_path}")

    artifact = joblib.load(model_path)
    if not isinstance(artifact, dict):
        raise RuntimeError("Model 5 artifact must be a dictionary")

    missing_keys = sorted(REQUIRED_ARTIFACT_KEYS - set(artifact.keys()))
    if missing_keys:
        raise RuntimeError(f"Model 5 artifact is missing keys: {', '.join(missing_keys)}")

    model = artifact.get("model")
    if model is None or not hasattr(model, "predict"):
        raise RuntimeError("Model 5 artifact does not contain a predict-capable model")

    return artifact


def validate_artifact_contract(artifact: dict[str, Any]) -> None:
    metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    model_family = artifact.get("model_family") or metadata.get("model_family")
    if model_family != EXPECTED_MODEL_FAMILY:
        raise RuntimeError(f"Expected model_family={EXPECTED_MODEL_FAMILY}, got {model_family!r}")

    if artifact.get("target_column") != TARGET_COLUMN:
        raise RuntimeError(f"Expected target_column={TARGET_COLUMN}, got {artifact.get('target_column')!r}")

    feature_columns = artifact.get("feature_columns")
    categorical_columns = artifact.get("categorical_columns")
    numeric_columns = artifact.get("numeric_columns")
    if feature_columns != FEATURE_COLUMNS:
        raise RuntimeError("Model 5 artifact feature_columns do not match the training feature policy")
    if categorical_columns != CATEGORICAL_FEATURE_COLUMNS:
        raise RuntimeError("Model 5 artifact categorical_columns do not match the training feature policy")
    if numeric_columns != NUMERIC_FEATURE_COLUMNS:
        raise RuntimeError("Model 5 artifact numeric_columns do not match the training feature policy")

    metadata_feature_columns = metadata.get("feature_columns")
    metadata_categorical_columns = metadata.get("categorical_columns")
    metadata_numeric_columns = metadata.get("numeric_columns")
    if metadata_feature_columns != feature_columns:
        raise RuntimeError("Model 5 metadata feature_columns do not match artifact feature_columns")
    if metadata_categorical_columns != categorical_columns:
        raise RuntimeError("Model 5 metadata categorical_columns do not match artifact categorical_columns")
    if metadata_numeric_columns != numeric_columns:
        raise RuntimeError("Model 5 metadata numeric_columns do not match artifact numeric_columns")

    forbidden = sorted(set(feature_columns) & (FORBIDDEN_FEATURE_COLUMNS | {TARGET_COLUMN, "priority_level"}))
    if forbidden:
        raise RuntimeError(f"Target leakage detected in feature_columns: {', '.join(forbidden)}")


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    positive_mask = y_true > 0
    mape = float(np.mean(np.abs((y_true[positive_mask] - y_pred[positive_mask]) / y_true[positive_mask]))) if np.any(positive_mask) else 0.0
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "mape": round(mape, 4),
    }


def _top_k_overlap(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for requested_k in TOP_K_VALUES:
        k = min(requested_k, len(y_true))
        if k <= 0:
            continue
        true_top = set(np.argsort(y_true)[-k:])
        predicted_top = set(np.argsort(y_pred)[-k:])
        overlap = len(true_top & predicted_top)
        result[f"top_{k}"] = {
            "k": k,
            "overlap_count": overlap,
            "overlap_ratio": round(overlap / k, 4),
        }
    return result


def _spearman_correlation(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float | None, str | None]:
    try:
        from scipy.stats import spearmanr
    except Exception:
        return None, "Spearman correlation skipped because scipy is not available."

    correlation, _p_value = spearmanr(y_true, y_pred)
    if correlation is None or math.isnan(float(correlation)):
        return None, "Spearman correlation skipped because one side was constant."
    return round(float(correlation), 4), None


def _ranking_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    spearman, note = _spearman_correlation(y_true, y_pred)
    metrics: dict[str, Any] = {
        "top_k_overlap": _top_k_overlap(y_true, y_pred),
        "spearman_correlation": spearman,
    }
    if note is not None:
        metrics["spearman_note"] = note
    return metrics


def _predict_scores(artifact: dict[str, Any], frame: pd.DataFrame) -> np.ndarray:
    model = artifact["model"]
    return np.array([_clamp_score(value) for value in model.predict(frame.loc[:, FEATURE_COLUMNS])], dtype=float)


def _train_test_evaluation(
    artifact: dict[str, Any],
    dataset_path: Path,
    *,
    test_size: float,
) -> tuple[int, int, int, dict[str, float], dict[str, float], dict[str, float], dict[str, Any]]:
    prepared = prepare_training_data(dataset_path)
    features = prepared.frame.loc[:, FEATURE_COLUMNS]
    target = prepared.frame[TARGET_COLUMN].astype(float)
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=test_size,
        random_state=RANDOM_STATE,
        shuffle=True,
    )

    train_predictions = _predict_scores(artifact, x_train)
    test_predictions = _predict_scores(artifact, x_test)
    y_train_values = y_train.to_numpy(dtype=float)
    y_test_values = y_test.to_numpy(dtype=float)

    train_metrics = _metrics(y_train_values, train_predictions)
    test_metrics = _metrics(y_test_values, test_predictions)
    gap = {
        "mae_gap": round(test_metrics["mae"] - train_metrics["mae"], 4),
        "rmse_gap": round(test_metrics["rmse"] - train_metrics["rmse"], 4),
        "r2_gap": round(train_metrics["r2"] - test_metrics["r2"], 4),
        "mape_gap": round(test_metrics["mape"] - train_metrics["mape"], 4),
    }
    ranking_metrics = _ranking_metrics(y_test_values, test_predictions)
    return (
        prepared.source_rows,
        len(x_train),
        len(x_test),
        train_metrics,
        test_metrics,
        gap,
        ranking_metrics,
    )


def _scenario(
    *,
    name: str,
    expected_behavior: str,
    rule_id: str,
    severity: str,
    category_name: str,
    impact_amount: float,
    impact_ratio: float,
    recurrence_count: float,
    days_since_generated: float,
    period_days: float,
    confidence_score: float,
    is_ml_generated: float,
    is_budget_related: float,
    is_fraud_related: float,
    is_forecast_related: float,
    is_income_related: float,
    is_profit_related: float,
    is_expense_related: float,
) -> tuple[str, str, dict[str, float | str]]:
    return (
        name,
        expected_behavior,
        {
            "rule_id": rule_id,
            "severity": severity,
            "impact_amount": impact_amount,
            "impact_ratio": impact_ratio,
            "recurrence_count": recurrence_count,
            "days_since_generated": days_since_generated,
            "period_days": period_days,
            "confidence_score": confidence_score,
            "is_ml_generated": is_ml_generated,
            "is_budget_related": is_budget_related,
            "is_fraud_related": is_fraud_related,
            "is_forecast_related": is_forecast_related,
            "is_income_related": is_income_related,
            "is_profit_related": is_profit_related,
            "is_expense_related": is_expense_related,
            "category_name": category_name,
        },
    )


def scenario_inputs() -> list[tuple[str, str, dict[str, float | str]]]:
    return [
        _scenario(
            name="Critical unusual transaction",
            expected_behavior="should rank very high",
            rule_id="ml_unusual_transaction",
            severity="critical",
            category_name="Marketing",
            impact_amount=95_000.0,
            impact_ratio=0.92,
            recurrence_count=1.0,
            days_since_generated=0.0,
            period_days=1.0,
            confidence_score=0.96,
            is_ml_generated=1.0,
            is_budget_related=0.0,
            is_fraud_related=1.0,
            is_forecast_related=0.0,
            is_income_related=0.0,
            is_profit_related=0.0,
            is_expense_related=1.0,
        ),
        _scenario(
            name="Critical profit drop",
            expected_behavior="should rank very high",
            rule_id="critical_profit_drop",
            severity="critical",
            category_name="Professional Services",
            impact_amount=48_000.0,
            impact_ratio=0.74,
            recurrence_count=2.0,
            days_since_generated=1.0,
            period_days=30.0,
            confidence_score=0.93,
            is_ml_generated=0.0,
            is_budget_related=0.0,
            is_fraud_related=0.0,
            is_forecast_related=0.0,
            is_income_related=0.0,
            is_profit_related=1.0,
            is_expense_related=0.0,
        ),
        _scenario(
            name="Repeated budget overspending",
            expected_behavior="should rank high",
            rule_id="repeated_budget_overspending",
            severity="warning",
            category_name="Marketing",
            impact_amount=9_500.0,
            impact_ratio=1.38,
            recurrence_count=5.0,
            days_since_generated=2.0,
            period_days=30.0,
            confidence_score=0.88,
            is_ml_generated=0.0,
            is_budget_related=1.0,
            is_fraud_related=0.0,
            is_forecast_related=0.0,
            is_income_related=0.0,
            is_profit_related=0.0,
            is_expense_related=1.0,
        ),
        _scenario(
            name="Forecast budget risk",
            expected_behavior="should rank high or medium-high",
            rule_id="ml_spending_forecast_risk",
            severity="warning",
            category_name="Office Supplies",
            impact_amount=12_000.0,
            impact_ratio=1.32,
            recurrence_count=2.0,
            days_since_generated=3.0,
            period_days=30.0,
            confidence_score=0.84,
            is_ml_generated=1.0,
            is_budget_related=1.0,
            is_fraud_related=0.0,
            is_forecast_related=1.0,
            is_income_related=0.0,
            is_profit_related=0.0,
            is_expense_related=1.0,
        ),
        _scenario(
            name="Budget recommendation",
            expected_behavior="should rank medium or high depending on impact",
            rule_id="ml_budget_recommendation",
            severity="info",
            category_name="Software",
            impact_amount=2_800.0,
            impact_ratio=0.28,
            recurrence_count=1.0,
            days_since_generated=5.0,
            period_days=30.0,
            confidence_score=0.72,
            is_ml_generated=1.0,
            is_budget_related=1.0,
            is_fraud_related=0.0,
            is_forecast_related=0.0,
            is_income_related=0.0,
            is_profit_related=0.0,
            is_expense_related=1.0,
        ),
        _scenario(
            name="Small info insight",
            expected_behavior="should rank low or medium",
            rule_id="expense_ratio",
            severity="info",
            category_name="Utilities",
            impact_amount=45.0,
            impact_ratio=0.06,
            recurrence_count=1.0,
            days_since_generated=45.0,
            period_days=7.0,
            confidence_score=0.48,
            is_ml_generated=0.0,
            is_budget_related=0.0,
            is_fraud_related=0.0,
            is_forecast_related=0.0,
            is_income_related=0.0,
            is_profit_related=0.0,
            is_expense_related=1.0,
        ),
    ]


def score_scenarios(artifact: dict[str, Any]) -> list[ScenarioResult]:
    names: list[str] = []
    expected: list[str] = []
    rows: list[dict[str, float | str]] = []
    for name, expected_behavior, row in scenario_inputs():
        names.append(name)
        expected.append(expected_behavior)
        rows.append(row)

    frame = pd.DataFrame(rows).loc[:, FEATURE_COLUMNS]
    scores = _predict_scores(artifact, frame)
    return [
        ScenarioResult(
            name=name,
            expected_behavior=expected_behavior,
            predicted_score=round(float(score), 4),
            predicted_level=_priority_level(float(score)),
            features=row,
        )
        for name, expected_behavior, row, score in zip(names, expected, rows, scores, strict=True)
    ]


def _scenario_warnings(scenarios: list[ScenarioResult]) -> list[str]:
    by_name = {scenario.name: scenario for scenario in scenarios}
    warnings: list[str] = []

    critical_fraud = by_name["Critical unusual transaction"]
    critical_profit = by_name["Critical profit drop"]
    repeated_budget = by_name["Repeated budget overspending"]
    forecast_risk = by_name["Forecast budget risk"]
    budget_recommendation = by_name["Budget recommendation"]
    small_info = by_name["Small info insight"]

    if critical_fraud.predicted_score < 85.0:
        warnings.append("Critical unusual transaction scored below the critical band.")
    if critical_profit.predicted_score < 85.0:
        warnings.append("Critical profit drop scored below the critical band.")
    if repeated_budget.predicted_score < 70.0:
        warnings.append("Repeated budget overspending scored below the high band.")
    if forecast_risk.predicted_score < 60.0:
        warnings.append("Forecast budget risk scored lower than expected.")
    if budget_recommendation.predicted_score < 45.0:
        warnings.append("Budget recommendation scored below the medium band.")
    if small_info.predicted_score >= min(critical_fraud.predicted_score, critical_profit.predicted_score):
        warnings.append("Small info insight outranked a critical scenario.")
    if small_info.predicted_score >= repeated_budget.predicted_score:
        warnings.append("Small info insight outranked repeated budget overspending.")

    return warnings


def _quality_warnings(
    train_metrics: dict[str, float],
    test_metrics: dict[str, float],
    gap: dict[str, float],
    ranking_metrics: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if test_metrics["r2"] < 0.80:
        warnings.append(f"Low validation R2: {test_metrics['r2']:.4f}")
    if test_metrics["mae"] > 5.0:
        warnings.append(f"High validation MAE: {test_metrics['mae']:.4f}")
    if test_metrics["mape"] > 0.08:
        warnings.append(f"High validation MAPE: {test_metrics['mape']:.4f}")
    if gap["r2_gap"] > 0.08:
        warnings.append(f"Possible overfitting: R2 gap is {gap['r2_gap']:.4f}")
    if gap["mae_gap"] > max(2.0, train_metrics["mae"] * 0.75):
        warnings.append(f"Possible overfitting: MAE gap is {gap['mae_gap']:.4f}")

    top_20 = ranking_metrics.get("top_k_overlap", {}).get("top_20")
    if isinstance(top_20, dict) and float(top_20.get("overlap_ratio", 0.0)) < 0.10:
        warnings.append("Top-20 overlap is low; capped priority scores may make exact top-k ranking noisy.")

    return warnings


def _verdict(warnings: list[str], test_metrics: dict[str, float], scenarios: list[ScenarioResult]) -> Verdict:
    if test_metrics["r2"] < 0.60 or test_metrics["mae"] > 10.0:
        return "failed"
    critical_names = {"Critical unusual transaction", "Critical profit drop"}
    critical_scores = [scenario.predicted_score for scenario in scenarios if scenario.name in critical_names]
    small_info_score = next(scenario.predicted_score for scenario in scenarios if scenario.name == "Small info insight")
    if critical_scores and small_info_score >= min(critical_scores):
        return "failed"
    if warnings:
        top_k_only = all("Top-20 overlap is low" in warning for warning in warnings)
        return "ready" if top_k_only else "needs tuning"
    return "ready"


def validate_insight_ranker(
    model_path: Path = DEFAULT_MODEL_PATH,
    dataset_path: Path = DEFAULT_DATASET_PATH,
    *,
    test_size: float = 0.20,
) -> ValidationResult:
    artifact = load_artifact(model_path)
    validate_artifact_contract(artifact)
    (
        dataset_rows,
        train_rows,
        test_rows,
        train_metrics,
        test_metrics,
        gap,
        ranking_metrics,
    ) = _train_test_evaluation(artifact, dataset_path, test_size=test_size)
    scenarios = score_scenarios(artifact)
    warnings = [
        *_quality_warnings(train_metrics, test_metrics, gap, ranking_metrics),
        *_scenario_warnings(scenarios),
    ]
    verdict = _verdict(warnings, test_metrics, scenarios)

    return ValidationResult(
        model_path=model_path,
        dataset_path=dataset_path,
        dataset_rows=dataset_rows,
        train_rows=train_rows,
        test_rows=test_rows,
        feature_columns=list(artifact["feature_columns"]),
        categorical_columns=list(artifact["categorical_columns"]),
        numeric_columns=list(artifact["numeric_columns"]),
        train_metrics=train_metrics,
        test_metrics=test_metrics,
        train_test_gap=gap,
        ranking_metrics=ranking_metrics,
        scenario_results=scenarios,
        warnings=warnings,
        verdict=verdict,
    )


def print_validation_report(result: ValidationResult) -> None:
    print("BizMoneyAI Model 5 Insight Importance Ranker Validation")
    print(f"Artifact: {result.model_path}")
    print(f"Dataset: {result.dataset_path}")
    print(f"Rows evaluated: {result.dataset_rows}")
    print(f"Train rows: {result.train_rows}")
    print(f"Test rows: {result.test_rows}")
    print(f"Model family: {EXPECTED_MODEL_FAMILY}")
    print(f"Feature columns: {', '.join(result.feature_columns)}")
    print(f"Categorical columns: {', '.join(result.categorical_columns)}")
    print(f"Numeric columns: {', '.join(result.numeric_columns)}")
    print("Leakage check: priority_score and priority_level are not features")
    print("Regression metrics:")
    print(
        f"- train: MAE={result.train_metrics['mae']:.4f}, "
        f"RMSE={result.train_metrics['rmse']:.4f}, "
        f"R2={result.train_metrics['r2']:.4f}, "
        f"MAPE={result.train_metrics['mape']:.4f}"
    )
    print(
        f"- test: MAE={result.test_metrics['mae']:.4f}, "
        f"RMSE={result.test_metrics['rmse']:.4f}, "
        f"R2={result.test_metrics['r2']:.4f}, "
        f"MAPE={result.test_metrics['mape']:.4f}"
    )
    print("Train/test gap:")
    print(
        f"- MAE gap={result.train_test_gap['mae_gap']:.4f}, "
        f"RMSE gap={result.train_test_gap['rmse_gap']:.4f}, "
        f"R2 gap={result.train_test_gap['r2_gap']:.4f}, "
        f"MAPE gap={result.train_test_gap['mape_gap']:.4f}"
    )
    print("Ranking metrics:")
    spearman = result.ranking_metrics.get("spearman_correlation")
    if spearman is None:
        print(f"- Spearman: {result.ranking_metrics.get('spearman_note', 'skipped')}")
    else:
        print(f"- Spearman: {spearman:.4f}")
    for key, summary in result.ranking_metrics["top_k_overlap"].items():
        print(
            f"- {key}: overlap={summary['overlap_count']}/{summary['k']} "
            f"({summary['overlap_ratio']:.4f})"
        )
    print("Scenario ranking:")
    for scenario in sorted(result.scenario_results, key=lambda item: item.predicted_score, reverse=True):
        print(
            f"- {scenario.name}: score={scenario.predicted_score:.2f} "
            f"level={scenario.predicted_level} expected={scenario.expected_behavior}"
        )
    print("Warnings:")
    if result.warnings:
        for warning in result.warnings:
            print(f"- {warning}")
    else:
        print("- none")
    print(f"Final verdict: {result.verdict}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the BizMoneyAI Model 5 insight importance ranker.")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--test-size", type=float, default=0.20)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    validation_result = validate_insight_ranker(
        model_path=args.model_path,
        dataset_path=args.dataset_path,
        test_size=args.test_size,
    )
    print_validation_report(validation_result)
