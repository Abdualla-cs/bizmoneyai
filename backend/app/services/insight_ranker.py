from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import joblib
import pandas as pd

from app.models.ai_insight import AIInsight

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[1] / "ml" / "models" / "insight_ranker.joblib"
MODEL_FAMILY = "bizmoneyai_insight_importance_ranker"
MODEL_FEATURE_COLUMNS = [
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
PRIORITY_LEVELS = {"low", "medium", "high", "critical"}
SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}
CONFIDENCE_LEVEL_SCORES = {
    "high": 0.90,
    "medium": 0.72,
    "low": 0.55,
    "unavailable": 0.45,
}

PriorityLevel = Literal["low", "medium", "high", "critical"]


@dataclass(frozen=True)
class RankedInsight:
    insight: AIInsight
    priority_score: float
    priority_level: PriorityLevel
    priority_reason: str


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _safe_abs_float(value: Any, default: float = 0.0) -> float:
    return abs(_safe_float(value, default))


def _metadata(insight: AIInsight) -> dict[str, Any]:
    metadata = insight.metadata_json
    return metadata if isinstance(metadata, dict) else {}


def _date_today() -> date:
    return date.today()


def _priority_level(score: float) -> PriorityLevel:
    if score >= 85.0:
        return "critical"
    if score >= 70.0:
        return "high"
    if score >= 45.0:
        return "medium"
    return "low"


def _clamp_score(value: Any) -> float:
    return round(min(max(_safe_float(value), 0.0), 100.0), 4)


def _period_days(insight: AIInsight) -> float:
    try:
        return float(max((insight.period_end - insight.period_start).days + 1, 1))
    except Exception:
        return 1.0


def _days_since_generated(insight: AIInsight, today: date) -> float:
    created_at = insight.created_at
    if isinstance(created_at, datetime):
        return float(max((today - created_at.date()).days, 0))
    return 0.0


def _first_number(metadata: dict[str, Any], keys: tuple[str, ...], default: float = 0.0) -> float:
    for key in keys:
        if key in metadata and metadata[key] not in (None, ""):
            return _safe_float(metadata[key], default)
    return default


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator > 0 else 0.0


def _percent_to_ratio(value: float) -> float:
    return value / 100.0 if abs(value) > 1.0 else value


def _impact_amount(metadata: dict[str, Any]) -> float:
    direct = _first_number(
        metadata,
        (
            "impact_amount",
            "transaction_amount",
            "amount",
            "forecast_vs_budget",
            "overspend_amount",
            "expected_change_amount",
            "deficit_amount",
            "category_spend_amount",
            "category_spend",
        ),
        default=0.0,
    )
    if direct:
        return _safe_abs_float(direct)

    budget_gap = _safe_float(metadata.get("budget_spent")) - _safe_float(metadata.get("budget_amount"))
    recommendation_gap = _safe_float(metadata.get("recommended_budget")) - _safe_float(metadata.get("current_budget"))
    forecast_gap = _safe_float(metadata.get("predicted_next_month_expense")) - _safe_float(metadata.get("budget_total"))
    expense_gap = _safe_float(metadata.get("current_expense")) - _safe_float(metadata.get("previous_expense"))
    income_gap = _safe_float(metadata.get("previous_income")) - _safe_float(metadata.get("current_income"))
    profit_gap = _safe_float(metadata.get("previous_profit")) - _safe_float(metadata.get("current_profit"))
    return round(max(budget_gap, recommendation_gap, forecast_gap, expense_gap, income_gap, profit_gap, 0.0), 2)


def _impact_ratio(metadata: dict[str, Any]) -> float:
    direct = _first_number(
        metadata,
        (
            "impact_ratio",
            "budget_usage_ratio",
            "expected_change_percent",
            "expense_ratio",
            "category_income_ratio",
        ),
        default=0.0,
    )
    if direct:
        return abs(direct)

    for key in ("spending_spike_percent", "income_drop_percent", "profit_drop_percent"):
        if key in metadata:
            return abs(_percent_to_ratio(_safe_float(metadata[key])))

    predicted = _safe_float(metadata.get("predicted_next_month_expense"))
    budget_total = _safe_float(metadata.get("budget_total"))
    if predicted > 0 and budget_total > 0:
        return _ratio(predicted, budget_total)

    current_expense = _safe_float(metadata.get("current_expense"))
    current_income = _safe_float(metadata.get("current_income"))
    if current_expense > 0 and current_income > 0:
        return _ratio(current_expense, current_income)

    return abs(_safe_float(metadata.get("fraud_probability"), 0.0))


def _recurrence_count(metadata: dict[str, Any]) -> float:
    return max(
        _first_number(
            metadata,
            (
                "recurrence_count",
                "consecutive_overspend_count",
                "months_over_budget_6",
                "months_over_budget_3",
                "months_used",
            ),
            default=1.0,
        ),
        1.0,
    )


def _confidence_score(insight: AIInsight, metadata: dict[str, Any]) -> float:
    direct = _first_number(metadata, ("confidence_score", "fraud_probability"), default=-1.0)
    if direct >= 0.0:
        return min(max(direct, 0.0), 1.0)

    confidence_level = str(metadata.get("confidence_level") or "").strip().lower()
    if confidence_level in CONFIDENCE_LEVEL_SCORES:
        return CONFIDENCE_LEVEL_SCORES[confidence_level]

    if insight.severity == "critical":
        return 0.85
    if insight.severity == "warning":
        return 0.65
    return 0.50


def _category_name(metadata: dict[str, Any]) -> str:
    category = metadata.get("category_name")
    if isinstance(category, str) and category.strip():
        return category.strip()
    top_categories = metadata.get("top_reduction_categories")
    if isinstance(top_categories, list) and top_categories:
        first = str(top_categories[0]).strip()
        if first:
            return first
    return "overall"


def _normalized_rule_id(insight: AIInsight) -> str:
    return str(insight.rule_id or "unknown").strip() or "unknown"


def _source(metadata: dict[str, Any]) -> str:
    return str(metadata.get("source") or "").strip().lower()


def _is_ml_generated(rule_id: str, metadata: dict[str, Any]) -> float:
    source = _source(metadata)
    return 1.0 if rule_id.startswith("ml_") or source in {"spending_forecaster", "budget_recommender", "fraud_detector"} else 0.0


def _contains_any(value: str, parts: tuple[str, ...]) -> bool:
    return any(part in value for part in parts)


def _feature_flags(rule_id: str, metadata: dict[str, Any]) -> dict[str, float]:
    source = _source(metadata)
    combined = f"{rule_id} {source}".lower()
    is_fraud = _contains_any(combined, ("fraud", "unusual"))
    is_forecast = _contains_any(combined, ("forecast",))
    is_budget = _contains_any(combined, ("budget", "overspend")) or is_forecast
    is_income = _contains_any(combined, ("income", "zero_income"))
    is_profit = _contains_any(combined, ("profit", "balance"))
    is_expense = _contains_any(combined, ("expense", "spend", "budget", "unusual", "forecast"))
    return {
        "is_ml_generated": _is_ml_generated(rule_id, metadata),
        "is_budget_related": 1.0 if is_budget else 0.0,
        "is_fraud_related": 1.0 if is_fraud else 0.0,
        "is_forecast_related": 1.0 if is_forecast else 0.0,
        "is_income_related": 1.0 if is_income else 0.0,
        "is_profit_related": 1.0 if is_profit else 0.0,
        "is_expense_related": 1.0 if is_expense else 0.0,
    }


def _priority_reason(insight: AIInsight, features: dict[str, float | str]) -> str:
    if insight.severity == "critical":
        return "Critical severity"
    if _safe_float(features["is_ml_generated"]) and (
        _safe_float(features["is_fraud_related"]) or _safe_float(features["is_forecast_related"])
    ):
        return "ML-detected risk"
    if _is_repeated_issue(insight, features):
        return "Repeated issue"
    if _safe_float(features["impact_amount"]) >= 1_000.0 or _safe_float(features["impact_ratio"]) >= 1.0:
        return "High financial impact"
    if _safe_float(features["days_since_generated"]) <= 7.0:
        return "Recent insight"
    return "High financial impact" if _safe_float(features["impact_amount"]) > 0.0 else "Recent insight"


def _is_repeated_issue(insight: AIInsight, features: dict[str, float | str]) -> bool:
    rule_id = _normalized_rule_id(insight).lower()
    return (
        _safe_float(features.get("recurrence_count")) >= 2.0
        or "repeated" in rule_id
        or "consecutive" in rule_id
    )


class InsightRanker:
    def __init__(self, model_path: Path = MODEL_PATH, *, today_provider=_date_today) -> None:
        self.model_path = model_path
        self._today_provider = today_provider
        self._model: Any | None = None
        self._feature_columns: list[str] = []
        self._load_model()

    def _load_model(self) -> None:
        if not self.model_path.exists():
            logger.info("Insight ranker model not found at %s", self.model_path)
            return

        try:
            artifact = joblib.load(self.model_path)
        except Exception:
            logger.exception("Failed to load insight ranker model from %s", self.model_path)
            return

        if not isinstance(artifact, dict):
            logger.warning("Ignoring incompatible insight ranker artifact at %s", self.model_path)
            return

        metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
        model_family = metadata.get("model_family") or artifact.get("model_family")
        model = artifact.get("model")
        feature_columns = artifact.get("feature_columns")

        if model_family != MODEL_FAMILY:
            logger.warning("Ignoring unsupported insight ranker model family: %s", model_family)
            return
        if model is None or not hasattr(model, "predict"):
            logger.warning("Ignoring insight ranker artifact without prediction support")
            return
        if feature_columns != MODEL_FEATURE_COLUMNS:
            logger.warning("Ignoring insight ranker artifact with incompatible feature columns")
            return

        self._model = model
        self._feature_columns = list(feature_columns)
        logger.info("Insight ranker loaded from %s", self.model_path)

    def is_ready(self) -> bool:
        return self._model is not None and self._feature_columns == MODEL_FEATURE_COLUMNS

    def _feature_row(self, insight: AIInsight) -> dict[str, float | str]:
        metadata = _metadata(insight)
        rule_id = _normalized_rule_id(insight)
        flags = _feature_flags(rule_id, metadata)
        return {
            "rule_id": rule_id,
            "severity": str(insight.severity or "info"),
            "impact_amount": _impact_amount(metadata),
            "impact_ratio": _impact_ratio(metadata),
            "recurrence_count": _recurrence_count(metadata),
            "days_since_generated": _days_since_generated(insight, self._today_provider()),
            "period_days": _period_days(insight),
            "confidence_score": _confidence_score(insight, metadata),
            **flags,
            "category_name": _category_name(metadata),
        }

    def _predict_score(self, features: dict[str, float | str]) -> float:
        if not self.is_ready():
            return _fallback_score(features)
        try:
            frame = pd.DataFrame([features], columns=MODEL_FEATURE_COLUMNS)
            assert self._model is not None
            return _clamp_score(self._model.predict(frame)[0])
        except Exception:
            logger.exception("Insight ranker prediction failed; using fallback score")
            return _fallback_score(features)

    def score_insight(self, insight: AIInsight) -> RankedInsight:
        features = self._feature_row(insight)
        score = self._predict_score(features)
        return RankedInsight(
            insight=insight,
            priority_score=score,
            priority_level=_priority_level(score),
            priority_reason=_priority_reason(insight, features),
        )

    def rank_insights(self, insights: list[AIInsight]) -> list[RankedInsight]:
        ranked = [self.score_insight(insight) for insight in insights]
        if self.is_ready():
            return sorted(ranked, key=_model_sort_key, reverse=True)
        return sorted(ranked, key=_fallback_sort_key, reverse=True)


def _fallback_score(features: dict[str, float | str]) -> float:
    severity = str(features.get("severity") or "info")
    severity_base = {"critical": 86.0, "warning": 62.0, "info": 38.0}.get(severity, 38.0)
    band_bonus = 0.0
    if _safe_float(features.get("is_fraud_related")):
        band_bonus += 6.0
    if _safe_float(features.get("recurrence_count")) >= 2.0:
        band_bonus += 4.0
    impact_amount = _safe_float(features.get("impact_amount"))
    impact_ratio = _safe_float(features.get("impact_ratio"))
    band_bonus += min(math.log10(max(impact_amount, 1.0)) * 1.5, 5.0)
    band_bonus += min(max(impact_ratio, 0.0) * 2.0, 4.0)
    if _safe_float(features.get("days_since_generated")) <= 7.0:
        band_bonus += 1.0
    return _clamp_score(severity_base + band_bonus)


def _created_sort_value(insight: AIInsight) -> float:
    created_at = insight.created_at
    if isinstance(created_at, datetime):
        return created_at.timestamp()
    return 0.0


def _insight_id_value(insight: AIInsight) -> int:
    try:
        return int(insight.insight_id or 0)
    except (TypeError, ValueError):
        return 0


def _model_sort_key(item: RankedInsight) -> tuple[float, float, int]:
    return (item.priority_score, _created_sort_value(item.insight), _insight_id_value(item.insight))


def _fallback_sort_key(item: RankedInsight) -> tuple[int, int, int, float, float, int]:
    features = _runtime_features_for_sort(item.insight)
    return (
        SEVERITY_RANK.get(str(item.insight.severity or "info"), 0),
        1 if _safe_float(features["is_fraud_related"]) else 0,
        1 if _is_repeated_issue(item.insight, features) else 0,
        _safe_float(features["impact_amount"]),
        _created_sort_value(item.insight),
        _insight_id_value(item.insight),
    )


def _runtime_features_for_sort(insight: AIInsight) -> dict[str, float | str]:
    metadata = _metadata(insight)
    rule_id = _normalized_rule_id(insight)
    flags = _feature_flags(rule_id, metadata)
    return {
        "is_fraud_related": flags["is_fraud_related"],
        "recurrence_count": _recurrence_count(metadata),
        "impact_amount": _impact_amount(metadata),
    }


ranker = InsightRanker()


def is_ready() -> bool:
    return ranker.is_ready()


def score_insight(insight: AIInsight) -> RankedInsight:
    return ranker.score_insight(insight)


def rank_insights(insights: list[AIInsight]) -> list[RankedInsight]:
    return ranker.rank_insights(insights)
