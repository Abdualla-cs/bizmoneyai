from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


DEFAULT_RAW_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "raw"
    / "paysim"
    / "PS_20174392719_1491204439457_log.csv"
)
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "processed"
    / "paysim_fraud_processed.csv"
)

REQUIRED_COLUMNS = [
    "step",
    "type",
    "amount",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
    "isFraud",
]

BASE_FEATURE_COLUMNS = [
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
]
TARGET_COLUMN = "isFraud"


def _validate_columns(columns: list[str], dataset_path: Path) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"{dataset_path} is missing required columns: {missing}")


def _format_float(value: float) -> str:
    return f"{value:.6f}"


def _parse_float(row: dict[str, str], column: str, line_number: int) -> float:
    raw_value = row.get(column)
    if raw_value in (None, ""):
        raise ValueError(f"Missing value for {column!r} on CSV line {line_number}")
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid numeric value for {column!r} on CSV line {line_number}: "
            f"{raw_value!r}"
        ) from exc


def _inspect_source(dataset_path: Path) -> tuple[list[str], Counter[str]]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"PaySim dataset not found at {dataset_path}")

    type_counts: Counter[str] = Counter()
    with dataset_path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        columns = reader.fieldnames or []
        _validate_columns(columns, dataset_path)

        for line_number, row in enumerate(reader, start=2):
            transaction_type = row.get("type")
            if transaction_type in (None, ""):
                raise ValueError(f"Missing value for 'type' on CSV line {line_number}")
            type_counts[transaction_type] += 1

    return sorted(type_counts), type_counts


def prepare_dataset(dataset_path: Path, output_path: Path) -> None:
    transaction_types, _type_counts = _inspect_source(dataset_path)
    type_feature_columns = [f"type_{transaction_type}" for transaction_type in transaction_types]
    feature_columns = BASE_FEATURE_COLUMNS + type_feature_columns
    output_columns = feature_columns + [TARGET_COLUMN]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    row_count = 0
    target_counts: Counter[str] = Counter()

    try:
        with (
            dataset_path.open("r", newline="", encoding="utf-8") as source_fh,
            temp_output_path.open("w", newline="", encoding="utf-8") as output_fh,
        ):
            reader = csv.DictReader(source_fh)
            columns = reader.fieldnames or []
            _validate_columns(columns, dataset_path)

            writer = csv.DictWriter(output_fh, fieldnames=output_columns)
            writer.writeheader()

            for line_number, row in enumerate(reader, start=2):
                amount = _parse_float(row, "amount", line_number)
                step = _parse_float(row, "step", line_number)
                oldbalance_org = _parse_float(row, "oldbalanceOrg", line_number)
                newbalance_orig = _parse_float(row, "newbalanceOrig", line_number)
                oldbalance_dest = _parse_float(row, "oldbalanceDest", line_number)
                newbalance_dest = _parse_float(row, "newbalanceDest", line_number)
                transaction_type = row.get("type")
                target = row.get(TARGET_COLUMN)

                if transaction_type in (None, ""):
                    raise ValueError(
                        f"Missing value for 'type' on CSV line {line_number}"
                    )
                if target in (None, ""):
                    raise ValueError(
                        f"Missing value for {TARGET_COLUMN!r} on CSV line "
                        f"{line_number}"
                    )

                processed_row = {
                    "amount": _format_float(amount),
                    "step": _format_float(step),
                    "oldbalanceOrg": _format_float(oldbalance_org),
                    "newbalanceOrig": _format_float(newbalance_orig),
                    "oldbalanceDest": _format_float(oldbalance_dest),
                    "newbalanceDest": _format_float(newbalance_dest),
                    "orig_balance_delta": _format_float(
                        oldbalance_org - newbalance_orig
                    ),
                    "dest_balance_delta": _format_float(
                        newbalance_dest - oldbalance_dest
                    ),
                    "orig_error": _format_float(
                        oldbalance_org - amount - newbalance_orig
                    ),
                    "dest_error": _format_float(
                        oldbalance_dest + amount - newbalance_dest
                    ),
                    TARGET_COLUMN: target,
                }

                for known_type in transaction_types:
                    processed_row[f"type_{known_type}"] = (
                        "1" if transaction_type == known_type else "0"
                    )

                writer.writerow(processed_row)
                row_count += 1
                target_counts[target] += 1

        temp_output_path.replace(output_path)
    except Exception:
        if temp_output_path.exists():
            temp_output_path.unlink()
        raise

    print(f"Processed dataset path: {output_path}")
    print(f"Processed dataset shape: ({row_count}, {len(output_columns)})")
    print("Feature columns:")
    for column in feature_columns:
        print(f"- {column}")

    print("Target distribution:")
    for target, count in sorted(target_counts.items()):
        print(f"- {target}: {count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the raw PaySim dataset for fraud detection modeling."
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=DEFAULT_RAW_DATASET_PATH,
        help="Path to the raw PaySim CSV file.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path where the processed PaySim CSV should be written.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    prepare_dataset(args.dataset_path, args.output_path)
