from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.ai_insight import AIInsight
from app.services.insights.calculator import build_insight_context
from app.services.insights.dedup import dedupe_candidates
from app.services.insights.rules import evaluate_rules


def generate_insights_for_user(
    db: Session,
    *,
    user_id: int,
    period_start: date,
    period_end: date,
) -> list[AIInsight]:
    context = build_insight_context(
        db,
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
    )
    candidates = evaluate_rules(context)
    new_candidates = dedupe_candidates(
        db,
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
        candidates=candidates,
    )
    if not new_candidates:
        return []

    created: list[AIInsight] = []
    for candidate in new_candidates:
        insight = AIInsight(
            user_id=user_id,
            rule_id=candidate.rule_id,
            title=candidate.title,
            message=candidate.message,
            severity=candidate.severity,
            period_start=period_start,
            period_end=period_end,
            metadata_json=candidate.metadata,
        )
        db.add(insight)
        created.append(insight)

    db.commit()
    for insight in created:
        db.refresh(insight)
    return created
