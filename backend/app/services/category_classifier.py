from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Any

import joblib
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[1] / "ml" / "models" / "classifier.joblib"
MIN_CONFIDENCE = 0.50
FUZZY_MATCH_CUTOFF = 0.80


@dataclass(frozen=True)
class CategoryPrediction:
    predicted_label: str
    matched_category: str
    confidence: float


def normalize_category_name(value: str) -> str:
    normalized = value.casefold().replace("&", " and ")
    return re.sub(r"\s+", " ", normalized).strip()


class CategoryClassifier:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model_path = model_path
        self._model: Pipeline | None = None
        self._load_model()

    def _load_model(self) -> None:
        if not self.model_path.exists():
            logger.info("Category classifier model not found at %s", self.model_path)
            return

        try:
            model = joblib.load(self.model_path)
        except Exception:
            logger.exception("Failed to load category classifier model from %s", self.model_path)
            return

        if not isinstance(model, Pipeline) or not hasattr(model, "predict_proba"):
            logger.warning("Ignoring incompatible category classifier model at %s", self.model_path)
            return

        self._model = model
        logger.info("Category classifier loaded from %s", self.model_path)

    def is_ready(self) -> bool:
        return self._model is not None

    def _match_user_category(self, predicted_name: str, user_categories: list[str]) -> str | None:
        category_lookup = {
            normalize_category_name(category): category.strip()
            for category in user_categories
            if category and category.strip()
        }
        if not category_lookup:
            return None

        normalized_prediction = normalize_category_name(predicted_name)
        exact_match = category_lookup.get(normalized_prediction)
        if exact_match is not None:
            return exact_match

        fuzzy_matches = get_close_matches(
            normalized_prediction,
            list(category_lookup.keys()),
            n=1,
            cutoff=FUZZY_MATCH_CUTOFF,
        )
        if not fuzzy_matches:
            return None
        return category_lookup[fuzzy_matches[0]]

    def predict(self, text: str, user_categories: list[str]) -> CategoryPrediction | None:
        if not self._model or not text.strip() or not user_categories:
            return None

        try:
            probabilities = self._model.predict_proba([text])[0]
            classes: Any = self._model.classes_
            best_index = int(probabilities.argmax())
            predicted_name = str(classes[best_index]).strip()
            confidence = round(float(probabilities[best_index]), 4)
            if confidence < MIN_CONFIDENCE:
                return None

            matched_name = self._match_user_category(predicted_name, user_categories)
            if matched_name is None:
                return None

            return CategoryPrediction(
                predicted_label=predicted_name,
                matched_category=matched_name,
                confidence=confidence,
            )
        except Exception:
            logger.exception("Category classifier prediction failed")
            return None


classifier = CategoryClassifier()


def is_ready() -> bool:
    return classifier.is_ready()


def predict(text: str, user_categories: list[str]) -> CategoryPrediction | None:
    return classifier.predict(text, user_categories)
