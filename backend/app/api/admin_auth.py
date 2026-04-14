from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import settings
from app.core.security import create_admin_access_token, verify_password
from app.db.session import get_db
from app.models.admin import Admin
from app.schemas.admin import AdminLogin, AdminOut
from app.services.admin_analytics import invalidate_admin_analytics_cache
from app.services.system_log import log_system_event

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])
protected_router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
protected_auth_router = APIRouter(prefix="/auth", tags=["admin-auth"])


def _normalize_email(value: str) -> str:
    return value.strip().lower()


@router.post("/login", response_model=AdminOut)
def login(payload: AdminLogin, response: Response, db: Session = Depends(get_db)):
    normalized_email = _normalize_email(str(payload.email))
    admin = db.query(Admin).filter(func.lower(Admin.email) == normalized_email).first()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_admin_access_token(str(admin.admin_id), timedelta(minutes=settings.access_token_expire_minutes))
    response.set_cookie(
        key="admin_access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.use_secure_cookies,
        max_age=settings.access_token_expire_minutes * 60,
    )
    log_system_event(
        db,
        "admin_login",
        f"Admin login succeeded for {admin.email}",
        admin_id=admin.admin_id,
        entity_id=admin.admin_id,
        metadata={"admin_email": admin.email},
    )
    db.commit()
    invalidate_admin_analytics_cache()
    return admin


@protected_auth_router.get("/me", response_model=AdminOut)
def me(current_admin: Admin = Depends(require_admin)):
    return current_admin


@protected_auth_router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="admin_access_token",
        httponly=True,
        samesite="lax",
        secure=settings.use_secure_cookies,
    )
    return {"message": "Logged out"}


protected_router.include_router(protected_auth_router)
