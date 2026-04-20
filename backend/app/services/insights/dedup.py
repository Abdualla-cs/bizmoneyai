from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.ai_insight import AIInsight
from app.services.insights.rules import InsightCandidate


def dedupe_candidates(
    db: Session,
    *,
    user_id: int,
    period_start: date,
    period_end: date,
    candidates: list[InsightCandidate],
) -> list[InsightCandidate]:
    if not candidates:
        return []

    relevant_rule_ids = {candidate.rule_id for candidate in candidates}
    existing_signatures = {
        _signature_for_insight(insight)
        for insight in (
            db.query(AIInsight)
            .filter(
                AIInsight.user_id == user_id,
                AIInsight.period_start == period_start,
                AIInsight.period_end == period_end,
                AIInsight.rule_id.in_(relevant_rule_ids),
            )
            .all()
        )
    }

    deduped: list[InsightCandidate] = []
    seen_signatures = set(existing_signatures)
    for candidate in candidates:
        signature = (candidate.rule_id, candidate.scope_key)
        if signature in seen_signatures:
            continue
        deduped.append(candidate)
        seen_signatures.add(signature)
    return deduped


def _signature_for_insight(insight: AIInsight) -> tuple[str | None, str]:
    metadata = insight.metadata_json or {}
    return (
        insight.rule_id,
        str(metadata.get("scope_key") or "period"),
    )
