import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_webhooks_empty():
    response = client.get("/webhooks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

from api.sanitizer import sanitize_payload


def test_sanitizer_removes_blocked_keys():
    payload = {"item": "book", "password": "secret123", "token": "abc"}
    result = sanitize_payload(payload)
    assert "password" not in result
    assert "token" not in result
    assert result["item"] == "book"


def test_sanitizer_strips_script_tags():
    payload = {"message": "<script>alert('xss')</script>hello"}
    result = sanitize_payload(payload)
    assert "<script>" not in result["message"]
    assert "hello" in result["message"]