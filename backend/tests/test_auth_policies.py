from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.admin_auth as admin_auth_module
import app.api.auth as auth_module
from app.api.admin_auth import protected_router as admin_protected_router
from app.api.admin_auth import router as admin_auth_router
from app.api.auth import router as auth_router
from app.core.config import settings
from app.db.session import get_db
from app.models.admin import Admin
from app.models.user import User


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin_auth_router)
    app.include_router(admin_protected_router)
    app.include_router(auth_router)
    return app


def test_register_enforces_password_minimum_length(db_session, monkeypatch):
    monkeypatch.setattr(auth_module, "get_password_hash", lambda password: password)

    app = create_test_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    try:
        short_password_response = client.post(
            "/auth/register",
            json={"name": "Short Password", "email": "short@example.com", "password": "12345"},
        )
        assert short_password_response.status_code == 422
        assert "at least 6 characters" in short_password_response.json()["detail"][0]["msg"]

        valid_password_response = client.post(
            "/auth/register",
            json={"name": "Valid Password", "email": "valid@example.com", "password": "123456"},
        )
        assert valid_password_response.status_code == 201
        assert valid_password_response.json()["email"] == "valid@example.com"
    finally:
        app.dependency_overrides.clear()


def test_register_and_login_normalize_email_case_insensitively(db_session, monkeypatch):
    monkeypatch.setattr(auth_module, "get_password_hash", lambda password: password)
    monkeypatch.setattr(auth_module, "verify_password", lambda plain, hashed: plain == hashed)

    app = create_test_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    try:
        register_response = client.post(
            "/auth/register",
            json={"name": "Normalized User", "email": "MixedCase@Example.com", "password": "secret1"},
        )
        assert register_response.status_code == 201
        assert register_response.json()["email"] == "mixedcase@example.com"

        duplicate_response = client.post(
            "/auth/register",
            json={"name": "Duplicate User", "email": "mixedcase@example.com", "password": "secret1"},
        )
        assert duplicate_response.status_code == 400
        assert duplicate_response.json()["detail"] == "Email already registered"

        login_response = client.post(
            "/auth/login",
            json={"email": "MIXEDCASE@example.com", "password": "secret1"},
        )
        assert login_response.status_code == 200
        assert login_response.json()["email"] == "mixedcase@example.com"
        assert "access_token" in client.cookies

        stored_user = db_session.query(User).filter(User.email == "mixedcase@example.com").one()
        assert stored_user.email == "mixedcase@example.com"
    finally:
        app.dependency_overrides.clear()


def test_auth_cookies_use_secure_flag_when_enabled(db_session, monkeypatch):
    monkeypatch.setattr(admin_auth_module, "verify_password", lambda plain, hashed: plain == hashed)
    monkeypatch.setattr(auth_module, "verify_password", lambda plain, hashed: plain == hashed)
    monkeypatch.setattr(settings, "cookie_secure", True, raising=False)

    admin = Admin(name="Admin User", email="admin@example.com", password_hash="secret123")
    user = User(name="Cookie User", email="cookie@example.com", password_hash="secret123")
    db_session.add_all([admin, user])
    db_session.commit()

    app = create_test_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    try:
        user_login_response = client.post(
            "/auth/login",
            json={"email": "cookie@example.com", "password": "secret123"},
        )
        assert user_login_response.status_code == 200
        assert "secure" in user_login_response.headers.get("set-cookie", "").lower()

        admin_login_response = client.post(
            "/admin/auth/login",
            json={"email": "admin@example.com", "password": "secret123"},
        )
        assert admin_login_response.status_code == 200
        assert "secure" in admin_login_response.headers.get("set-cookie", "").lower()
    finally:
        app.dependency_overrides.clear()
