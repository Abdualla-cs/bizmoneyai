from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

import app.api.ml as ml_api
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.category import Category
from app.models.system_log import SystemLog
from app.models.user import User
from app.services.category_classifier import CategoryClassifier
from app.services.category_classifier import CategoryPrediction


@dataclass
class FakeModel:
    classes_: np.ndarray
    probabilities: np.ndarray

    def predict_proba(self, texts):
        return np.vstack([self.probabilities for _text in texts])


class FakeClassifier:
    def __init__(self, prediction: CategoryPrediction | None):
        self.prediction = prediction

    def predict(self, text: str, user_categories: list[str]):
        return self.prediction


def _authenticated_ml_client(db_session):
    user = User(name="ML Test User", email="ml-test@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    categories = [
        Category(user_id=user.user_id, name="Food & Dining", type="expense"),
        Category(user_id=user.user_id, name="Transportation", type="expense"),
    ]
    db_session.add_all(categories)
    db_session.commit()
    for category in categories:
        db_session.refresh(category)

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))
    return client, user, categories


def test_classifier_missing_model_does_not_crash(tmp_path):
    classifier = CategoryClassifier(model_path=tmp_path / "missing-classifier.joblib")

    assert classifier.is_ready() is False
    assert classifier.predict("Uber ride to airport", ["Transportation"]) is None


def test_classifier_low_confidence_returns_none_for_fallback():
    classifier = CategoryClassifier(model_path=Path(__file__).with_suffix(".missing"))
    classifier._model = FakeModel(  # type: ignore[assignment]
        classes_=np.array(["Transportation"]),
        probabilities=np.array([0.49]),
    )

    assert classifier.predict("unclear transaction", ["Transportation", "Rent"]) is None


def test_classifier_matches_normalized_and_fuzzy_user_category_names():
    classifier = CategoryClassifier(model_path=Path(__file__).with_suffix(".missing"))

    classifier._model = FakeModel(  # type: ignore[assignment]
        classes_=np.array(["Food and Dining"]),
        probabilities=np.array([0.91]),
    )
    normalized_match = classifier.predict("team lunch", ["Food & Dining"])
    assert normalized_match == CategoryPrediction(
        predicted_label="Food and Dining",
        matched_category="Food & Dining",
        confidence=0.91,
    )

    classifier._model = FakeModel(  # type: ignore[assignment]
        classes_=np.array(["Office Supplies"]),
        probabilities=np.array([0.88]),
    )
    fuzzy_match = classifier.predict("printer paper", ["Office Supply"])
    assert fuzzy_match == CategoryPrediction(
        predicted_label="Office Supplies",
        matched_category="Office Supply",
        confidence=0.88,
    )


def test_ml_route_preserves_response_schema_and_logs_classifier_prediction(db_session, monkeypatch):
    client, user, categories = _authenticated_ml_client(db_session)
    monkeypatch.setattr(
        ml_api,
        "classifier",
        FakeClassifier(
            CategoryPrediction(
                predicted_label="Food and Dining",
                matched_category="Food & Dining",
                confidence=0.93,
            )
        ),
    )

    try:
        response = client.post("/ml/predict-category", json={"text": "Team lunch at pizza place"})

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"suggested_category_id", "suggested_category_name", "confidence"}
        assert body == {
            "suggested_category_id": categories[0].category_id,
            "suggested_category_name": "Food & Dining",
            "confidence": 0.93,
        }

        log = db_session.query(SystemLog).filter(SystemLog.user_id == user.user_id).one()
        assert log.event_type == "ml_category_prediction"
        assert log.metadata_json["method"] == "classifier"
        assert log.metadata_json["predicted_label"] == "Food and Dining"
        assert log.metadata_json["matched_category"] == "Food & Dining"
    finally:
        app.dependency_overrides.clear()


def test_ml_route_falls_back_when_classifier_returns_none(db_session, monkeypatch):
    client, _user, categories = _authenticated_ml_client(db_session)
    monkeypatch.setattr(ml_api, "classifier", FakeClassifier(None))
    monkeypatch.setattr(
        ml_api,
        "embed_texts",
        lambda texts: np.array(
            [
                [1.0, 0.0],
                [0.0, 1.0],
                [1.0, 0.0],
            ]
        ),
    )

    try:
        response = client.post("/ml/predict-category", json={"text": "Uber ride to airport"})

        assert response.status_code == 200
        assert response.json() == {
            "suggested_category_id": categories[1].category_id,
            "suggested_category_name": "Transportation",
            "confidence": 1.0,
        }
    finally:
        app.dependency_overrides.clear()
