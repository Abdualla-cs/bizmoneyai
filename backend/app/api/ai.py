from datetime import date, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.data_access import InsightQueryFilters, list_insights_for_user, query_insight_timeseries
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai_insight import AIInsightGenerateRequest, AIInsightOut, AIInsightTimeSeriesPoint
from app.services.admin_analytics import invalidate_admin_analytics_cache
from app.services.rules_engine import run_rules_for_user
from app.services.system_log import log_system_event

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate", response_model=list[AIInsightOut])
def generate_insights(
    payload: AIInsightGenerateRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    end = payload.period_end if payload and payload.period_end is not None else date.today()
    start = payload.period_start if payload and payload.period_start is not None else end - timedelta(days=30)
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_start must be on or before period_end",
        )

    created = run_rules_for_user(db, current_user.user_id, start, end)
    log_system_event(
        db,
        "generate_insights",
        f"Generated {len(created)} insights for period {start.isoformat()} to {end.isoformat()}",
        user_id=current_user.user_id,
        metadata={
            "generated_count": len(created),
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
        },
    )
    db.commit()
    invalidate_admin_analytics_cache()
    return created


@router.get("/insights", response_model=list[AIInsightOut])
def list_insights(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    severity: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be on or before date_to",
        )
    return list_insights_for_user(
        db,
        InsightQueryFilters(
            user_id=current_user.user_id,
            date_from=date_from,
            date_to=date_to,
            severity=severity,
        ),
    )


@router.get("/insights/timeseries", response_model=list[AIInsightTimeSeriesPoint])
def list_insight_timeseries(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    severity: str | None = Query(default=None),
    granularity: str = Query(default="day"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if granularity not in {"day", "month"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="granularity must be 'day' or 'month'",
        )
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must be on or before date_to",
        )
    return query_insight_timeseries(
        db,
        InsightQueryFilters(
            user_id=current_user.user_id,
            date_from=date_from,
            date_to=date_to,
            severity=severity,
        ),
        granularity=granularity,
    )
