"""Unit tests for POST /users endpoint."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers import users as users_router


@pytest.fixture(autouse=True)
def clear_store():
    """Reset in-memory store before each test."""
    users_router._users.clear()
    yield
    users_router._users.clear()


client = TestClient(app)


def test_create_user_success():
    resp = client.post("/users", json={"name": "Alice", "email": "alice@example.com"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"
    assert "id" in data


def test_create_user_returns_unique_ids():
    r1 = client.post("/users", json={"name": "Bob", "email": "bob@example.com"})
    r2 = client.post("/users", json={"name": "Carol", "email": "carol@example.com"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


def test_create_user_duplicate_email_returns_409():
    client.post("/users", json={"name": "Dave", "email": "dave@example.com"})
    resp = client.post("/users", json={"name": "Dave2", "email": "dave@example.com"})
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


def test_create_user_missing_name_returns_422():
    resp = client.post("/users", json={"email": "noname@example.com"})
    assert resp.status_code == 422


def test_create_user_invalid_email_returns_422():
    resp = client.post("/users", json={"name": "Eve", "email": "not-an-email"})
    assert resp.status_code == 422


def test_create_user_empty_name_returns_422():
    resp = client.post("/users", json={"name": "", "email": "empty@example.com"})
    assert resp.status_code == 422


def test_create_user_response_schema():
    resp = client.post("/users", json={"name": "Frank", "email": "frank@example.com"})
    assert resp.status_code == 201
    data = resp.json()
    assert set(data.keys()) == {"id", "name", "email"}
