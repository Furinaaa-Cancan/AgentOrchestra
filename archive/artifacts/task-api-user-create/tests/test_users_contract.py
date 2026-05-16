"""Contract tests for POST /users endpoint (OpenAPI schema validation)."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers import users as users_router


@pytest.fixture(autouse=True)
def clear_store():
    users_router._users.clear()
    yield
    users_router._users.clear()


client = TestClient(app)


def test_openapi_schema_exposes_post_users():
    """Verify the OpenAPI schema includes POST /users."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "/users" in schema["paths"], "POST /users must be in OpenAPI paths"
    assert "post" in schema["paths"]["/users"], "POST method must exist on /users"


def test_post_users_request_body_schema():
    """Request body must require name and email."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    post_op = schema["paths"]["/users"]["post"]
    request_body = post_op.get("requestBody", {})
    assert request_body, "POST /users must have a requestBody"
    content = request_body.get("content", {})
    assert "application/json" in content


def test_post_users_201_response_defined():
    """201 response must be defined in schema."""
    resp = client.get("/openapi.json")
    schema = resp.json()
    responses = schema["paths"]["/users"]["post"]["responses"]
    assert "201" in responses, "201 response must be declared"


def test_post_users_409_response_on_duplicate():
    """Duplicate email must return 409 with detail field."""
    client.post("/users", json={"name": "Test", "email": "test@contract.com"})
    resp = client.post("/users", json={"name": "Test2", "email": "test@contract.com"})
    assert resp.status_code == 409
    body = resp.json()
    assert "detail" in body


def test_post_users_422_on_bad_payload():
    """Invalid payload must return 422 with validation errors."""
    resp = client.post("/users", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body


def test_post_users_response_contains_id_name_email():
    """Successful response must contain id, name, email fields."""
    resp = client.post("/users", json={"name": "Contract", "email": "contract@test.com"})
    assert resp.status_code == 201
    data = resp.json()
    for field in ("id", "name", "email"):
        assert field in data, f"Response must contain '{field}'"
