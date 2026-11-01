"""Isolated database fixtures for backend API tests."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register every model on metadata
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def csrf_headers(client: TestClient) -> dict[str, str]:
    """Return a valid CSRF header, initializing the cookie when needed."""
    token = client.cookies.get("iem_csrf")
    if not token:
        token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return {"X-CSRF-Token": token}


def register_account(client: TestClient, *, email: str = "owner@example.com", organization: str = "Northwind Trade") -> dict:
    client.get("/api/v1/auth/csrf")
    response = client.post(
        "/api/v1/auth/register",
        headers=csrf_headers(client),
        json={
            "email": email,
            "full_name": "Test Owner",
            "password": "correct-horse-battery-12",
            "organization_name": organization,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
