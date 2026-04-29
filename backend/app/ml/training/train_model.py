from __future__ import annotations

import csv
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

DATA_PATH = Path(__file__).resolve().parent / "training_data.csv"
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "classifier.joblib"
OVERFITTING_WARNING_GAP = 0.08

OOD_VALIDATION_EXAMPLES = [
    ("paid meta campaign invoice", "Marketing"),
    ("monthly aws cloud bill", "Software"),
    ("grabbed coffee for client meeting", "Food & Dining"),
    ("uber airport ride", "Transportation"),
    ("office lease april payment", "Rent"),
    ("printer ink and paper", "Office Supplies"),
    ("client invoice payment received", "Income"),
]


def _load_training_rows() -> tuple[list[str], list[str]]:
    with DATA_PATH.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        descriptions: list[str] = []
        categories: list[str] = []
        for row in reader:
            description = (row.get("description") or "").strip()
            category = (row.get("category") or "").strip()
            if not description or not category:
                continue
            descriptions.append(description)
            categories.append(category)

    if not descriptions:
        raise RuntimeError(f"No training rows found in {DATA_PATH}")
    return descriptions, categories


def train() -> Pipeline:
    descriptions, categories = _load_training_rows()
    category_names = sorted(set(categories))

    print(f"Rows: {len(descriptions)}")
    print(f"Categories: {', '.join(category_names)}")

    x_train, x_test, y_train, y_test = train_test_split(
        descriptions,
        categories,
        test_size=0.2,
        random_state=42,
        stratify=categories,
    )

    pipeline = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=5000)),
            ("classifier", LogisticRegression(max_iter=2000)),
        ]
    )
    pipeline.fit(x_train, y_train)

    train_predictions = pipeline.predict(x_train)
    test_predictions = pipeline.predict(x_test)
    train_accuracy = accuracy_score(y_train, train_predictions)
    test_accuracy = accuracy_score(y_test, test_predictions)
    accuracy_gap = train_accuracy - test_accuracy

    print(f"Train accuracy: {train_accuracy:.4f}")
    print(f"Test accuracy: {test_accuracy:.4f}")
    print(f"Train/test accuracy gap: {accuracy_gap:.4f}")
    if accuracy_gap > OVERFITTING_WARNING_GAP:
        print(
            "WARNING: Train accuracy is much higher than test accuracy. "
            "The classifier may be overfitting the training data."
        )

    print("Classification report:")
    print(classification_report(y_test, test_predictions, zero_division=0))
    print("Confusion matrix:")
    print("Labels:", ", ".join(category_names))
    print(confusion_matrix(y_test, test_predictions, labels=category_names))

    print("Out-of-distribution validation:")
    validation_texts = [text for text, _expected in OOD_VALIDATION_EXAMPLES]
    validation_predictions = pipeline.predict(validation_texts)
    validation_probabilities = pipeline.predict_proba(validation_texts)
    for index, (text, expected) in enumerate(OOD_VALIDATION_EXAMPLES):
        predicted = str(validation_predictions[index])
        confidence = float(validation_probabilities[index].max())
        status = "OK" if predicted == expected else "MISS"
        print(
            f"- {status} text={text!r} expected={expected!r} "
            f"predicted={predicted!r} confidence={confidence:.4f}"
        )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"Saved model to {MODEL_PATH}")
    return pipeline


if __name__ == "__main__":
    train()
