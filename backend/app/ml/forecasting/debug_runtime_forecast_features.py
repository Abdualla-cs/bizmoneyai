from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import joblib

from app.db.session import SessionLocal
from app.ml.forecasting.train_spending_forecaster import SCENARIO_SEQUENCE
from app.services.spending_forecaster import (
    MODEL_PATH,
    MonthSnapshot,
    SpendingForecaster,
)


def _shift_month(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def _synthetic_snapshots(sequence: list[float]) -> list[MonthSnapshot]:
    snapshots: list[MonthSnapshot] = []
    for index, amount in enumerate(sequence):
        month_start = date(2026, index + 1, 1)
        snapshot = MonthSnapshot(
            month_start=month_start,
            total_income=round(amount * 1.8, 2),
            clean_total_expense=amount,
            transaction_count=20,
            expense_transaction_count=15,
            income_transaction_count=5,
            budget_total=round(amount * 1.1, 2),
        )
        snapshot.category_ids = {1, 2, 3}
        snapshot.expense_by_category["Marketing"] = round(amount * 0.40, 2)
        snapshot.expense_by_category["Software"] = round(amount * 0.35, 2)
        snapshot.expense_by_category["Operations"] = round(amount * 0.25, 2)
        snapshots.append(snapshot)
    return snapshots


def _load_artifact(model_path: Path) -> dict[str, Any] | None:
    if not model_path.exists():
        return None
    artifact = joblib.load(model_path)
    return artifact if isinstance(artifact, dict) else None


def _print_debug_report(
    *,
    forecaster: SpendingForecaster,
    snapshots: list[MonthSnapshot],
    model_path: Path,
) -> None:
    if not snapshots:
        print("No monthly snapshots available.")
        return

    latest = snapshots[-1]
    snapshots_by_month = {snapshot.month_start: snapshot for snapshot in snapshots}
    previous_month = _shift_month(latest.month_start, -1)
    two_months_ago = _shift_month(latest.month_start, -2)
    feature_row = forecaster._build_feature_row(snapshots)
    artifact = _load_artifact(model_path)
    artifact_columns = list((artifact or {}).get("feature_columns") or [])
    model = (artifact or {}).get("model")
    prediction = None
    if model is not None and hasattr(model, "predict"):
        prediction = float(model.predict([feature_row])[0])

    def expense_for(month: date) -> float:
        snapshot = snapshots_by_month.get(month)
        return float(snapshot.clean_total_expense if snapshot else 0.0)

    print("BizMoneyAI Model 3 Runtime Forecast Feature Debug")
    print(f"model_path: {model_path}")
    print(f"model_ready: {forecaster.is_ready()}")
    print(f"artifact_feature_columns_match_runtime: {artifact_columns == forecaster._feature_columns}")
    print(f"months_used: {len(snapshots)}")
    print(f"latest_month: {latest.month_start.isoformat()}")
    print(f"current_month_expense: {latest.clean_total_expense:.2f}")
    print(f"previous_month_expense: {expense_for(previous_month):.2f}")
    print(f"expense_2_months_ago: {expense_for(two_months_ago):.2f}")
    print(f"rolling_3_month_expense_avg: {feature_row.get('rolling_3_month_expense_avg', 0.0):.2f}")
    print(f"rolling_6_month_expense_avg: {feature_row.get('rolling_6_month_expense_avg', 0.0):.2f}")
    print(f"expense_growth_rate: {feature_row.get('expense_growth_rate', 0.0):.6f}")
    print(f"expense_delta_1m: {feature_row.get('expense_delta_1m', 0.0):.2f}")
    print(f"expense_delta_2m: {feature_row.get('expense_delta_2m', 0.0):.2f}")
    print(f"monthly_expense_slope: {feature_row.get('monthly_expense_slope', 0.0):.2f}")
    print(f"last_3_month_growth_rate: {feature_row.get('last_3_month_growth_rate', 0.0):.6f}")
    print(f"current_vs_rolling_3_ratio: {feature_row.get('current_vs_rolling_3_ratio', 0.0):.6f}")
    print(f"budget_total: {latest.budget_total:.2f}")
    print(f"budget_usage_ratio: {latest.budget_usage_ratio:.6f}")
    print(f"budget_growth_rate: {feature_row.get('budget_growth_rate', 0.0):.6f}")
    print(f"top_categories: {', '.join(latest.top_expense_categories[:3]) or 'n/a'}")
    print("final_feature_vector:")
    print(json.dumps(feature_row, indent=2, sort_keys=True))
    print(f"prediction_result: {prediction:.2f}" if prediction is not None else "prediction_result: unavailable")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug Model 3 runtime forecast features.")
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH)
    parser.add_argument(
        "--sequence",
        type=str,
        default=",".join(str(value) for value in SCENARIO_SEQUENCE),
        help="Comma-separated synthetic monthly expenses used when --user-id is omitted.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    forecaster = SpendingForecaster(model_path=args.model_path)

    if args.user_id is not None:
        db = SessionLocal()
        try:
            snapshots = forecaster._monthly_snapshots(db, args.user_id)
        finally:
            db.close()
    else:
        sequence = [float(part.strip()) for part in args.sequence.split(",") if part.strip()]
        snapshots = _synthetic_snapshots(sequence)

    _print_debug_report(forecaster=forecaster, snapshots=snapshots, model_path=args.model_path)


if __name__ == "__main__":
    main()
