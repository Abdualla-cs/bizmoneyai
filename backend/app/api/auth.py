from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserOut
from app.services.admin_analytics import invalidate_admin_analytics_cache
from app.services.system_log import log_system_event

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(value: object) -> str:
    return str(value).strip().lower()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    normalized_email = _normalize_email(payload.email)
    existing = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=normalized_email,
        password_hash=get_password_hash(payload.password),
    )
    db.add(user)
    db.flush()
    log_system_event(
        db,
        "user_registration",
        f"User registered {user.email}",
        user_id=user.user_id,
        entity_id=user.user_id,
        metadata={"email": user.email},
    )
    db.commit()
    invalidate_admin_analytics_cache()
    db.refresh(user)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    normalized_email = _normalize_email(payload.email)
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    token = create_access_token(str(user.user_id), timedelta(minutes=settings.access_token_expire_minutes))
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.use_secure_cookies,
        max_age=settings.access_token_expire_minutes * 60,
    )
    log_system_event(
        db,
        "user_login",
        f"User login succeeded for {user.email}",
        user_id=user.user_id,
        entity_id=user.user_id,
        metadata={"email": user.email},
    )
    db.commit()
    invalidate_admin_analytics_cache()
    return user


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="lax",
        secure=settings.use_secure_cookies,
    )
    return {"message": "Logged out"}
