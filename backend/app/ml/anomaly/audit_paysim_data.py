from __future__ import annotations

import argparse
import csv
from array import array
from collections import Counter
from pathlib import Path

import numpy as np


DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "raw"
    / "paysim"
    / "PS_20174392719_1491204439457_log.csv"
)


def _format_percentage(value: float) -> str:
    return f"{value:.4f}%"


def audit_dataset(dataset_path: Path) -> None:
    if not dataset_path.exists():
        raise FileNotFoundError(f"PaySim dataset not found at {dataset_path}")

    row_count = 0
    columns: list[str] = []
    missing_counts: Counter[str] = Counter()
    fraud_counts: Counter[str] = Counter()
    transaction_type_counts: Counter[str] = Counter()
    amounts = array("d")

    with dataset_path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        columns = reader.fieldnames or []

        for row in reader:
            row_count += 1

            for column in columns:
                if row.get(column) in (None, ""):
                    missing_counts[column] += 1

            fraud_counts[row.get("isFraud", "")] += 1
            transaction_type_counts[row.get("type", "")] += 1

            amount = row.get("amount")
            if amount not in (None, ""):
                amounts.append(float(amount))

    amount_values = np.frombuffer(amounts, dtype=np.float64)
    fraud_count = fraud_counts["1"]
    normal_count = fraud_counts["0"]
    fraud_percentage = (fraud_count / row_count) * 100 if row_count else 0.0

    print(f"Dataset path: {dataset_path}")
    print(f"Dataset shape: ({row_count}, {len(columns)})")
    print("Columns:")
    for column in columns:
        print(f"- {column}")

    print("Missing values:")
    for column in columns:
        print(f"- {column}: {missing_counts[column]}")

    print(f"Fraud count: {fraud_count}")
    print(f"Normal count: {normal_count}")
    print(f"Fraud percentage: {_format_percentage(fraud_percentage)}")

    print("Transaction type distribution:")
    for transaction_type, count in transaction_type_counts.most_common():
        print(f"- {transaction_type}: {count}")

    print("Amount statistics:")
    if len(amount_values) == 0:
        print("- min: n/a")
        print("- max: n/a")
        print("- mean: n/a")
        print("- median: n/a")
    else:
        print(f"- min: {amount_values.min():.2f}")
        print(f"- max: {amount_values.max():.2f}")
        print(f"- mean: {amount_values.mean():.2f}")
        print(f"- median: {np.median(amount_values):.2f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the raw PaySim fraud detection dataset."
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the PaySim CSV file.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    audit_dataset(args.dataset_path)
