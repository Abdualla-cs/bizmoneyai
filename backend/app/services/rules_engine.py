from datetime import date

from sqlalchemy.orm import Session

from app.models.ai_insight import AIInsight
from app.services.insights import generate_insights_for_user


def run_rules_for_user(db: Session, user_id: int, period_start: date, period_end: date) -> list[AIInsight]:
    return generate_insights_for_user(
        db,
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
    )
