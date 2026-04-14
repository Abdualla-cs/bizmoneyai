import logging
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.system_log import SystemLog
from app.services.admin_analytics import invalidate_admin_analytics_cache


def _first_non_none(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_log_metadata(
    metadata: dict[str, Any] | None,
    *,
    admin_id: int | None,
    user_id: int | None,
    entity_id: int | None,
) -> dict[str, Any] | None:
    if metadata is None and admin_id is None and user_id is None and entity_id is None:
        return None

    normalized = dict(metadata or {})
    normalized["user_id"] = _first_non_none(normalized.get("user_id"), user_id)
    normalized["admin_id"] = _first_non_none(normalized.get("admin_id"), admin_id)
    normalized["entity_id"] = _first_non_none(normalized.get("entity_id"), entity_id)
    return normalized


def log_system_event(
    db: Session,
    event_type: str,
    message: str,
    *,
    level: str = "info",
    admin_id: int | None = None,
    user_id: int | None = None,
    entity_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> SystemLog:
    entry = SystemLog(
        admin_id=admin_id,
        user_id=user_id,
        event_type=event_type,
        message=message,
        level=level,
        metadata_json=_normalize_log_metadata(
            metadata,
            admin_id=admin_id,
            user_id=user_id,
            entity_id=entity_id,
        ),
    )
    db.add(entry)
    return entry


def log_system_event_safe(
    event_type: str,
    message: str,
    *,
    level: str = "error",
    admin_id: int | None = None,
    user_id: int | None = None,
    entity_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db = SessionLocal()
    try:
        log_system_event(
            db,
            event_type,
            message,
            level=level,
            admin_id=admin_id,
            user_id=user_id,
            entity_id=entity_id,
            metadata=metadata,
        )
        db.commit()
        invalidate_admin_analytics_cache()
    except Exception:
        db.rollback()
        logging.getLogger("app.error").exception("Failed to persist system log event=%s", event_type)
    finally:
        db.close()
