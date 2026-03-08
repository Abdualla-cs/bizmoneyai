from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.ai_insight import AIInsight
from app.models.user import User
from app.schemas.ai_insight import AIInsightOut
from app.services.rules_engine import run_rules_for_user

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate", response_model=list[AIInsightOut])
def generate_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    end = date.today()
    start = end - timedelta(days=30)
    return run_rules_for_user(db, current_user.user_id, start, end)


@router.get("/insights", response_model=list[AIInsightOut])
def list_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(AIInsight)
        .filter(AIInsight.user_id == current_user.user_id)
        .order_by(AIInsight.created_at.desc())
        .all()
    )
