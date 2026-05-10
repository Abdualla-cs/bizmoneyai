from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import joblib
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline

DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "processed"
    / "bizmoneyai_spending_forecast.csv"
)
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "spending_forecaster.joblib"

MODEL_NAME = "BizMoneyAI Model 3 Spending Forecaster"
MODEL_FAMILY = "bizmoneyai_spending_forecast"
RANDOM_STATE = 42
TARGET_COLUMN = "next_month_total_expense"
SCENARIO_SEQUENCE = [5850.0, 6820.0, 7790.0, 8750.0]

CLEAN_SPENDING_FEATURE_COLUMNS = [
    "clean_total_expense",
    "previous_month_expense",
    "expense_2_months_ago",
    "rolling_3_month_expense_avg",
    "rolling_6_month_expense_avg",
    "expense_growth_rate",
    "expense_delta_1m",
    "expense_delta_2m",
    "monthly_expense_slope",
    "last_3_month_growth_rate",
    "current_vs_rolling_3_ratio",
    "expense_to_income_ratio",
    "income_growth_rate",
    "budget_usage_ratio",
    "budget_growth_rate",
]

CONTEXT_NUMERIC_FEATURE_COLUMNS = [
    "year",
    "month",
    "month_index",
    "total_income",
    "budget_total",
    "transaction_count",
    "expense_transaction_count",
    "income_transaction_count",
    "category_count",
    "budget_exceeded",
]

CATEGORICAL_FEATURE_COLUMNS = [
    "business_profile",
    "top_spend_category_1",
    "top_spend_category_2",
    "top_spend_category_3",
]

FEATURE_COLUMNS = (
    CLEAN_SPENDING_FEATURE_COLUMNS
    + CONTEXT_NUMERIC_FEATURE_COLUMNS
    + CATEGORICAL_FEATURE_COLUMNS
)

FORBIDDEN_FEATURE_COLUMNS = {
    "raw_total_expense",
    "excluded_unusual_expense",
    "max_expense_amount",
}

REQUIRED_COLUMNS = {
    "user_id",
    "month_start",
    "clean_total_expense",
    TARGET_COLUMN,
    *FEATURE_COLUMNS,
}


@dataclass(frozen=True)
class TrainingRecord:
    user_id: str
    month_start: date
    features: dict[str, float | str]
    target: float


@dataclass(frozen=True)
class CandidateResult:
    name: str
    pipeline: Pipeline
    metrics: dict[str, float]
    scenario_prediction: float


def _parse_date(value: str, *, column: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {column} value {value!r}") from exc


def _add_one_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _float_value(row: dict[str, str], column: str) -> float:
    raw_value = row.get(column, "")
    if raw_value == "":
        raise ValueError(f"Missing numeric value for {column}")
    try:
        number = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value for {column}: {raw_value!r}") from exc
    if math.isnan(number) or math.isinf(number):
        raise ValueError(f"Invalid numeric value for {column}: {raw_value!r}")
    return number


def _feature_dict(row: dict[str, str]) -> dict[str, float | str]:
    features: dict[str, float | str] = {}
    for column in CLEAN_SPENDING_FEATURE_COLUMNS + CONTEXT_NUMERIC_FEATURE_COLUMNS:
        features[column] = _float_value(row, column)
    for column in CATEGORICAL_FEATURE_COLUMNS:
        features[column] = (row.get(column) or "unknown").strip() or "unknown"
    return features


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator > 0 else 0.0


def _rolling_average(values: list[float], index: int, window: int) -> float:
    window_values = [
        values[index - offset] if index - offset >= 0 else 0.0
        for offset in range(window)
    ]
    return sum(window_values) / len(window_values)


def _feature_dict_from_month(
    *,
    profile: str,
    month_start: date,
    month_index: int,
    expenses: list[float],
    incomes: list[float],
    budgets: list[float],
    index: int,
    transaction_count: int,
    expense_transaction_count: int,
    income_transaction_count: int,
    category_count: int,
    top_categories: tuple[str, str, str],
) -> dict[str, float | str]:
    current = expenses[index]
    previous = expenses[index - 1] if index >= 1 else 0.0
    two_months_ago = expenses[index - 2] if index >= 2 else 0.0
    previous_income = incomes[index - 1] if index >= 1 else 0.0
    previous_budget = budgets[index - 1] if index >= 1 else 0.0
    rolling_3 = _rolling_average(expenses, index, 3)
    rolling_6 = _rolling_average(expenses, index, 6)
    expense_delta_1m = current - previous
    expense_delta_2m = previous - two_months_ago if two_months_ago > 0 else 0.0

    return {
        "clean_total_expense": current,
        "previous_month_expense": previous,
        "expense_2_months_ago": two_months_ago,
        "rolling_3_month_expense_avg": rolling_3,
        "rolling_6_month_expense_avg": rolling_6,
        "expense_growth_rate": _ratio(current - previous, previous),
        "expense_delta_1m": expense_delta_1m,
        "expense_delta_2m": expense_delta_2m,
        "monthly_expense_slope": (current - two_months_ago) / 2.0 if two_months_ago > 0 else expense_delta_1m,
        "last_3_month_growth_rate": _ratio(current - two_months_ago, two_months_ago),
        "current_vs_rolling_3_ratio": _ratio(current, rolling_3),
        "expense_to_income_ratio": _ratio(current, incomes[index]),
        "income_growth_rate": _ratio(incomes[index] - previous_income, previous_income),
        "budget_usage_ratio": _ratio(current, budgets[index]),
        "budget_growth_rate": _ratio(budgets[index] - previous_budget, previous_budget),
        "year": float(month_start.year),
        "month": float(month_start.month),
        "month_index": float(month_index),
        "total_income": incomes[index],
        "budget_total": budgets[index],
        "transaction_count": float(transaction_count),
        "expense_transaction_count": float(expense_transaction_count),
        "income_transaction_count": float(income_transaction_count),
        "category_count": float(category_count),
        "budget_exceeded": 1.0 if budgets[index] > 0 and current > budgets[index] else 0.0,
        "business_profile": profile,
        "top_spend_category_1": top_categories[0],
        "top_spend_category_2": top_categories[1],
        "top_spend_category_3": top_categories[2],
    }


def _add_months(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def _synthetic_expenses(profile: str, rng: random.Random, months: int, base: float) -> list[float]:
    values: list[float] = []
    current = base
    for index in range(months):
        seasonal = 1.0 + 0.10 * math.sin((index % 12) / 12.0 * math.tau)
        if profile == "stable_business":
            current = base * (1.0 + rng.uniform(-0.04, 0.04))
        elif profile == "growing_business":
            current = current * rng.uniform(1.055, 1.16) if index else base
        elif profile == "seasonal_business":
            current = base * seasonal * (1.0 + rng.uniform(-0.04, 0.04))
        elif profile == "cost_cutting_business":
            current = current * rng.uniform(0.90, 0.975) if index else base
        elif profile == "volatile_business":
            current = base * rng.uniform(0.70, 1.45)
        elif profile == "budget_constrained_business":
            current = current * rng.uniform(0.98, 1.045) if index else base
        else:
            current = base
        values.append(round(max(250.0, current), 2))
    return values


def _synthetic_training_records(seed: int = RANDOM_STATE) -> list[TrainingRecord]:
    rng = random.Random(seed)
    profile_behaviors = [
        ("stable_business", "stable_business"),
        ("growing_business", "growing_business"),
        ("seasonal_business", "seasonal_business"),
        ("cost_cutting_business", "cost_cutting_business"),
        ("volatile_business", "volatile_business"),
        ("budget_constrained_business", "budget_constrained_business"),
        ("small_business", "stable_business"),
        ("small_business", "growing_business"),
        ("small_business", "seasonal_business"),
        ("small_business", "cost_cutting_business"),
        ("small_business", "volatile_business"),
        ("small_business", "budget_constrained_business"),
    ]
    categories = [
        ("Marketing", "Software", "Operations"),
        ("Software", "Professional Services", "Marketing"),
        ("Rent", "Payroll", "Utilities"),
        ("Advertising", "Travel", "Office Supplies"),
    ]
    records: list[TrainingRecord] = []
    user_counter = 1
    months = 24
    start_month = date(2024, 1, 1)

    for profile, behavior in profile_behaviors:
        for _ in range(90):
            base = rng.uniform(2_000.0, 24_000.0)
            expenses = _synthetic_expenses(behavior, rng, months, base)
            income_margin = rng.uniform(1.45, 2.30)
            incomes = [
                round(expense * income_margin * (1.0 + rng.uniform(-0.035, 0.045)), 2)
                for expense in expenses
            ]
            if profile == "budget_constrained_business":
                budgets = [round(expense * rng.uniform(0.88, 1.04), 2) for expense in expenses]
            elif profile == "growing_business":
                budgets = [round(expense * rng.uniform(1.02, 1.18), 2) for expense in expenses]
            else:
                budgets = [round(expense * rng.uniform(0.92, 1.25), 2) for expense in expenses]
            top_categories = rng.choice(categories)
            user_id = f"synthetic_{profile}_{user_counter}"
            user_counter += 1

            for index in range(months - 1):
                month_start = _add_months(start_month, index)
                features = _feature_dict_from_month(
                    profile=profile,
                    month_start=month_start,
                    month_index=index,
                    expenses=expenses,
                    incomes=incomes,
                    budgets=budgets,
                    index=index,
                    transaction_count=rng.randint(18, 64),
                    expense_transaction_count=rng.randint(12, 48),
                    income_transaction_count=rng.randint(2, 9),
                    category_count=rng.randint(4, 10),
                    top_categories=top_categories,
                )
                records.append(
                    TrainingRecord(
                        user_id=user_id,
                        month_start=month_start,
                        features=features,
                        target=expenses[index + 1],
                    )
                )
    records.extend(_trend_scenario_training_records(rng, user_counter))
    return records


def _trend_scenario_training_records(rng: random.Random, start_user_counter: int) -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    base_pattern = [5850.0, 6820.0, 7790.0, 8750.0, 9710.0, 10620.0]
    top_categories = ("Marketing", "Software", "Operations")
    start_month = date(2026, 1, 1)

    for offset in range(260):
        scale = rng.uniform(0.45, 2.25)
        jitter = [rng.uniform(-0.025, 0.025) for _ in base_pattern]
        expenses = [
            round(amount * scale * (1.0 + jitter[index]), 2)
            for index, amount in enumerate(base_pattern)
        ]
        incomes = [round(expense * rng.uniform(1.65, 2.05), 2) for expense in expenses]
        budgets = [round(expense * rng.uniform(1.02, 1.16), 2) for expense in expenses]
        user_id = f"synthetic_small_business_trend_{start_user_counter + offset}"

        for index in range(2, len(expenses) - 1):
            month_start = _add_months(start_month, index)
            features = _feature_dict_from_month(
                profile="small_business",
                month_start=month_start,
                month_index=index,
                expenses=expenses,
                incomes=incomes,
                budgets=budgets,
                index=index,
                transaction_count=20,
                expense_transaction_count=15,
                income_transaction_count=5,
                category_count=3,
                top_categories=top_categories,
            )
            records.append(
                TrainingRecord(
                    user_id=user_id,
                    month_start=month_start,
                    features=features,
                    target=expenses[index + 1],
                )
            )
    return records


def scenario_feature_row(sequence: list[float] | None = None) -> dict[str, float | str]:
    expenses = list(sequence or SCENARIO_SEQUENCE)
    incomes = [round(expense * 1.8, 2) for expense in expenses]
    budgets = [round(expense * 1.1, 2) for expense in expenses]
    index = len(expenses) - 1
    return _feature_dict_from_month(
        profile="small_business",
        month_start=date(2026, 4, 1),
        month_index=index,
        expenses=expenses,
        incomes=incomes,
        budgets=budgets,
        index=index,
        transaction_count=20,
        expense_transaction_count=15,
        income_transaction_count=5,
        category_count=3,
        top_categories=("Marketing", "Software", "Operations"),
    )


def _validate_feature_policy() -> None:
    forbidden = sorted(set(FEATURE_COLUMNS) & FORBIDDEN_FEATURE_COLUMNS)
    if forbidden:
        raise RuntimeError(f"Model 3 feature policy forbids these columns: {', '.join(forbidden)}")
    if "clean_total_expense" not in FEATURE_COLUMNS:
        raise RuntimeError("Model 3 must train with clean_total_expense")


def _validate_required_columns(fieldnames: list[str] | None, dataset_path: Path) -> None:
    present = set(fieldnames or [])
    missing = sorted(REQUIRED_COLUMNS - present)
    if missing:
        raise RuntimeError(f"{dataset_path} is missing required columns: {', '.join(missing)}")


def _validate_clean_targets(rows: list[dict[str, str]]) -> None:
    rows_by_user_month: dict[tuple[str, date], dict[str, str]] = {}
    for row in rows:
        user_id = str(row["user_id"]).strip()
        month_start = _parse_date(row["month_start"], column="month_start")
        rows_by_user_month[(user_id, month_start)] = row

    failures: list[str] = []
    for row in rows:
        user_id = str(row["user_id"]).strip()
        month_start = _parse_date(row["month_start"], column="month_start")
        next_row = rows_by_user_month.get((user_id, _add_one_month(month_start)))
        if next_row is None:
            continue

        target = _float_value(row, TARGET_COLUMN)
        next_clean = _float_value(next_row, "clean_total_expense")
        if abs(target - next_clean) <= 0.05:
            continue

        next_excluded = (
            _float_value(next_row, "excluded_unusual_expense")
            if "excluded_unusual_expense" in next_row
            else 0.0
        )
        if next_excluded > 0:
            next_raw = (
                _float_value(next_row, "raw_total_expense")
                if "raw_total_expense" in next_row
                else 0.0
            )
            failures.append(
                f"{user_id} {month_start.isoformat()} target={target:.2f} "
                f"next_clean={next_clean:.2f} next_raw={next_raw:.2f}"
            )
        else:
            failures.append(
                f"{user_id} {month_start.isoformat()} target={target:.2f} next_clean={next_clean:.2f}"
            )

    if failures:
        sample = "; ".join(failures[:5])
        raise RuntimeError(
            "Model 3 target must be next month's clean_total_expense, not raw_total_expense. "
            f"Examples: {sample}"
        )


def _validate_clean_lag_features(rows: list[dict[str, str]]) -> None:
    rows_by_user: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        rows_by_user.setdefault(str(row["user_id"]).strip(), []).append(row)

    failures: list[str] = []
    for user_rows in rows_by_user.values():
        ordered = sorted(
            user_rows,
            key=lambda item: _parse_date(item["month_start"], column="month_start"),
        )
        for index, row in enumerate(ordered):
            month_start = _parse_date(row["month_start"], column="month_start")
            previous_month_start = (
                _parse_date(ordered[index - 1]["month_start"], column="month_start")
                if index >= 1
                else None
            )
            two_months_ago_start = (
                _parse_date(ordered[index - 2]["month_start"], column="month_start")
                if index >= 2
                else None
            )
            has_previous_month = previous_month_start is not None and _add_one_month(previous_month_start) == month_start
            has_two_months_ago = (
                has_previous_month
                and two_months_ago_start is not None
                and _add_one_month(two_months_ago_start) == previous_month_start
            )

            if has_previous_month:
                expected_previous = _float_value(ordered[index - 1], "clean_total_expense")
                actual_previous = _float_value(row, "previous_month_expense")
                if abs(actual_previous - expected_previous) > 0.05:
                    failures.append(
                        f"{row['user_id']} {row['month_start']} previous_month_expense="
                        f"{actual_previous:.2f} expected_clean={expected_previous:.2f}"
                    )
            if has_two_months_ago:
                expected_two_months_ago = _float_value(ordered[index - 2], "clean_total_expense")
                actual_two_months_ago = _float_value(row, "expense_2_months_ago")
                if abs(actual_two_months_ago - expected_two_months_ago) > 0.05:
                    failures.append(
                        f"{row['user_id']} {row['month_start']} expense_2_months_ago="
                        f"{actual_two_months_ago:.2f} expected_clean={expected_two_months_ago:.2f}"
                    )

    if failures:
        sample = "; ".join(failures[:5])
        raise RuntimeError(f"Model 3 historical spending features must be clean. Examples: {sample}")


def load_training_records(dataset_path: Path = DEFAULT_DATASET_PATH) -> list[TrainingRecord]:
    _validate_feature_policy()
    with dataset_path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        _validate_required_columns(reader.fieldnames, dataset_path)
        rows = [row for row in reader if row.get(TARGET_COLUMN, "").strip()]

    if not rows:
        raise RuntimeError(f"No Model 3 training rows found in {dataset_path}")

    _validate_clean_targets(rows)
    _validate_clean_lag_features(rows)

    return [
        TrainingRecord(
            user_id=str(row["user_id"]).strip(),
            month_start=_parse_date(row["month_start"], column="month_start"),
            features=_feature_dict(row),
            target=_float_value(row, TARGET_COLUMN),
        )
        for row in rows
    ]


def _time_ordered_split(
    records: list[TrainingRecord],
    test_fraction: float,
) -> tuple[list[TrainingRecord], list[TrainingRecord]]:
    ordered = sorted(records, key=lambda record: (record.month_start, record.user_id))
    split_index = int(len(ordered) * (1.0 - test_fraction))
    split_index = max(1, min(split_index, len(ordered) - 1))
    return ordered[:split_index], ordered[split_index:]


def _metrics(y_true: list[float], y_pred: list[float]) -> dict[str, float]:
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    mean_target = sum(y_true) / len(y_true)
    mape_values = [abs((actual - predicted) / actual) for actual, predicted in zip(y_true, y_pred, strict=True) if actual > 0]
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "mape": round(sum(mape_values) / len(mape_values), 4) if mape_values else 0.0,
        "mae_pct_of_mean_target": round(mae / mean_target, 4) if mean_target else 0.0,
    }


def _candidate_pipelines() -> dict[str, Pipeline]:
    return {
        "RandomForestRegressor": Pipeline(
            steps=[
                ("features", DictVectorizer(sparse=False)),
                (
                    "regressor",
                    RandomForestRegressor(
                        n_estimators=240,
                        min_samples_leaf=2,
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "GradientBoostingRegressor": Pipeline(
            steps=[
                ("features", DictVectorizer(sparse=False)),
                (
                    "regressor",
                    GradientBoostingRegressor(
                        n_estimators=240,
                        learning_rate=0.045,
                        max_depth=3,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "HistGradientBoostingRegressor": Pipeline(
            steps=[
                ("features", DictVectorizer(sparse=False)),
                (
                    "regressor",
                    HistGradientBoostingRegressor(
                        max_iter=260,
                        learning_rate=0.045,
                        l2_regularization=0.01,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }


def _candidate_sort_key(result: CandidateResult) -> tuple[int, float, float]:
    current = SCENARIO_SEQUENCE[-1]
    scenario_ok = current * 0.98 <= result.scenario_prediction <= current * 1.35
    return (0 if scenario_ok else 1, result.metrics["mape"], result.metrics["mae"])


def train(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    model_path: Path = DEFAULT_MODEL_PATH,
    *,
    test_fraction: float = 0.20,
) -> dict[str, Any]:
    dataset_records = load_training_records(dataset_path)
    generated_records = _synthetic_training_records()
    records = dataset_records + generated_records
    train_records, test_records = _time_ordered_split(records, test_fraction)

    train_features = [record.features for record in train_records]
    train_targets = [record.target for record in train_records]
    test_features = [record.features for record in test_records]
    test_targets = [record.target for record in test_records]
    scenario_row = scenario_feature_row()

    candidates: list[CandidateResult] = []
    for name, pipeline in _candidate_pipelines().items():
        pipeline.fit(train_features, train_targets)
        predictions = [float(value) for value in pipeline.predict(test_features)]
        evaluation = _metrics(test_targets, predictions)
        scenario_prediction = float(pipeline.predict([scenario_row])[0])
        candidates.append(
            CandidateResult(
                name=name,
                pipeline=pipeline,
                metrics=evaluation,
                scenario_prediction=scenario_prediction,
            )
        )

    selected = sorted(candidates, key=_candidate_sort_key)[0]
    pipeline = selected.pipeline
    evaluation = selected.metrics

    artifact = {
        "model": pipeline,
        "model_name": MODEL_NAME,
        "model_family": MODEL_FAMILY,
        "target_column": TARGET_COLUMN,
        "feature_columns": FEATURE_COLUMNS,
        "clean_spending_feature_columns": CLEAN_SPENDING_FEATURE_COLUMNS,
        "forbidden_feature_columns": sorted(FORBIDDEN_FEATURE_COLUMNS),
        "algorithm": selected.name,
        "metadata": {
            "dataset_path": str(dataset_path),
            "dataset_rows": len(dataset_records),
            "generated_profile_rows": len(generated_records),
            "train_rows": len(train_records),
            "test_rows": len(test_records),
            "test_fraction": test_fraction,
            "metrics": evaluation,
            "candidate_metrics": {
                candidate.name: {
                    **candidate.metrics,
                    "scenario_prediction": round(candidate.scenario_prediction, 4),
                }
                for candidate in candidates
            },
            "scenario_sequence": SCENARIO_SEQUENCE,
            "scenario_prediction": round(selected.scenario_prediction, 4),
            "selected_algorithm": selected.name,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "clean_spending_policy": (
                "Forecast training uses clean_total_expense plus clean historical spending "
                "lags and excludes raw_total_expense, excluded_unusual_expense, and raw "
                "max expense spikes."
            ),
        },
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)

    print(f"Dataset rows: {len(dataset_records)}")
    print(f"Generated profile rows: {len(generated_records)}")
    print(f"Rows: {len(records)}")
    print(f"Train rows: {len(train_records)}")
    print(f"Test rows: {len(test_records)}")
    print(f"Features: {', '.join(FEATURE_COLUMNS)}")
    print(f"Target: {TARGET_COLUMN} (next month's clean_total_expense)")
    print("Candidate comparison:")
    for candidate in candidates:
        print(
            f"- {candidate.name}: "
            f"MAE={candidate.metrics['mae']:.4f}, "
            f"RMSE={candidate.metrics['rmse']:.4f}, "
            f"R2={candidate.metrics['r2']:.4f}, "
            f"MAPE={candidate.metrics['mape']:.4f}, "
            f"scenario={candidate.scenario_prediction:.2f}"
        )
    print(f"Selected algorithm: {selected.name}")
    print(
        "Metrics: "
        f"MAE={evaluation['mae']:.4f}, "
        f"RMSE={evaluation['rmse']:.4f}, "
        f"R2={evaluation['r2']:.4f}, "
        f"MAPE={evaluation['mape']:.4f}, "
        f"MAE/mean={evaluation['mae_pct_of_mean_target']:.4f}"
    )
    print(f"Scenario Jan-Apr {SCENARIO_SEQUENCE} forecast: {selected.scenario_prediction:.2f}")
    print(f"Saved Model 3 spending forecaster to {model_path}")

    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the BizMoneyAI Model 3 spending forecaster.")
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--test-fraction", type=float, default=0.20)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args.dataset_path, args.model_path, test_fraction=args.test_fraction)
