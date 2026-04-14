from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.admin_auth as admin_auth_module
from app.api.admin_auth import protected_router as admin_protected_router
from app.api.admin_auth import router as admin_auth_router
from app.api.auth import router as auth_router
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.admin import Admin
from app.models.user import User


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin_auth_router)
    app.include_router(admin_protected_router)
    app.include_router(auth_router)
    return app


def test_admin_auth_uses_admin_cookie_and_admin_table(db_session, monkeypatch):
    monkeypatch.setattr(admin_auth_module, "verify_password", lambda plain, hashed: plain == hashed)

    admin = Admin(
        name="Admin User",
        email="admin@example.com",
        password_hash="secret123",
    )
    user = User(
        name="Regular User",
        email="user@example.com",
        password_hash="secret123",
    )
    db_session.add_all([admin, user])
    db_session.commit()

    app = create_test_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    try:
        login_response = client.post(
            "/admin/auth/login",
            json={"email": "admin@example.com", "password": "secret123"},
        )

        assert login_response.status_code == 200
        assert "admin_access_token" in client.cookies
        set_cookie = login_response.headers.get("set-cookie", "").lower()
        assert "admin_access_token=" in set_cookie
        assert "httponly" in set_cookie
        assert login_response.json()["email"] == "admin@example.com"

        me_response = client.get("/admin/auth/me")
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "admin@example.com"

        user_me_response = client.get("/auth/me")
        assert user_me_response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_admin_login_does_not_authenticate_regular_users(db_session, monkeypatch):
    monkeypatch.setattr(admin_auth_module, "verify_password", lambda plain, hashed: plain == hashed)

    user = User(
        name="Regular User",
        email="shared@example.com",
        password_hash="secret123",
    )
    db_session.add(user)
    db_session.commit()

    app = create_test_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    try:
        response = client.post(
            "/admin/auth/login",
            json={"email": "shared@example.com", "password": "secret123"},
        )

        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_admin_routes_return_403_for_normal_users(db_session):
    user = User(
        name="Regular User",
        email="member@example.com",
        password_hash="secret123",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    app = create_test_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    client.cookies.set("access_token", create_access_token(str(user.user_id)))

    try:
        response = client.get("/admin/auth/me")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_routes_return_401_without_auth(db_session):
    app = create_test_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    try:
        response = client.get("/admin/auth/me")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
