import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api.main import get_db


# ----------------------------
# Setup
# ----------------------------

@pytest.fixture
def client():

    with patch("api.main.SessionLocal"), \
         patch("api.main.Base.metadata.create_all"), \
         patch("api.main.redis_client") as mock_redis, \
         patch("api.tracing.setup_tracing"), \
         patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app"):

        mock_redis.get.return_value = None
        mock_redis.llen.return_value = 0
        mock_redis.lpush.return_value = 1
        mock_redis.set.return_value = True
        mock_redis.incr.return_value = 1
        mock_redis.ttl.return_value = 0

        from api.main import app

        yield TestClient(app), mock_redis

        app.dependency_overrides = {}


# ----------------------------
# Test 1 — Health
# ----------------------------

def test_health(client):
    test_client, _ = client

    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ----------------------------
# Test 2 — Webhook CRUD
# ----------------------------

def test_register_webhook(client):
    test_client, _ = client

    mock_session = MagicMock()

    from api.main import app

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = test_client.post(
        "/webhooks",
        json={
            "user_id": "user1",
            "url": "http://example.com/webhook",
            "event_types": ["order.created"]
        }
    )

    assert response.status_code == 200


def test_list_webhooks(client):
    test_client, _ = client

    mock_session = MagicMock()
    mock_session.query.return_value.all.return_value = []

    from api.main import app

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = test_client.get("/webhooks")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_delete_webhook_not_found(client):
    test_client, _ = client

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None

    from api.main import app

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = test_client.delete("/webhooks/999")

    assert response.status_code == 404


def test_disable_webhook(client):
    test_client, _ = client

    mock_webhook = MagicMock()
    mock_webhook.active = True

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_webhook

    from api.main import app

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = test_client.patch("/webhooks/1/disable")

    assert response.status_code == 200
    assert mock_webhook.active is False


def test_enable_webhook(client):
    test_client, _ = client

    mock_webhook = MagicMock()
    mock_webhook.active = False

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_webhook

    from api.main import app

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = test_client.patch("/webhooks/1/enable")

    assert response.status_code == 200
    assert mock_webhook.active is True


# ----------------------------
# Test 3 — Event Queue
# ----------------------------

def test_event_queued_per_user(client):
    test_client, mock_redis = client

    mock_webhook = MagicMock()
    mock_webhook.id = 1
    mock_webhook.user_id = "user1"
    mock_webhook.url = "http://example.com/webhook"
    mock_webhook.event_types = ["order.created"]
    mock_webhook.active = True

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_webhook]

    from api.main import app

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = test_client.post(
        "/events",
        json={
            "user_id": "user1",
            "event_type": "order.created",
            "payload": {"item": "book"}
        }
    )

    assert response.status_code == 200
    assert response.json()["deliveries_created"] == 1

    mock_redis.lpush.assert_called_once()

    queue_name = mock_redis.lpush.call_args[0][0]
    assert "webhook_queue_user1" in queue_name


def test_event_not_queued_for_unsubscribed_type(client):
    test_client, mock_redis = client

    mock_webhook = MagicMock()
    mock_webhook.event_types = ["order.updated"]
    mock_webhook.active = True

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_webhook]

    from api.main import app

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = test_client.post(
        "/events",
        json={
            "user_id": "user1",
            "event_type": "order.created",
            "payload": {"item": "book"}
        }
    )

    assert response.status_code == 200
    assert response.json()["deliveries_created"] == 0

    mock_redis.lpush.assert_not_called()


# ----------------------------
# Test 4 — Retry
# ----------------------------

def test_delivery_retries_on_failure():

    with patch("api.worker.worker.requests.post") as mock_post, \
         patch("api.worker.worker.redis_client"), \
         patch("api.worker.worker.time.sleep"), \
         patch("api.worker.worker.setup_tracing"), \
         patch("api.worker.worker.RequestsInstrumentor"):

        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200

        mock_post.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success
        ]

        mock_webhook = MagicMock()
        mock_webhook.url = "http://example.com/webhook"
        mock_webhook.user_id = "user1"

        mock_delivery = MagicMock()
        mock_delivery.payload = "{}"
        mock_delivery.event_type = "order.created"

        from api.worker.worker import deliver_with_retry

        result = deliver_with_retry(mock_webhook, mock_delivery, 1)

    assert result is True
    assert mock_post.call_count == 3


# ----------------------------
# Test 5 — DLQ
# ----------------------------

def test_dlq():

    with patch("api.worker.worker.redis_client") as mock_redis:

        from api.worker.worker import send_to_dlq

        send_to_dlq({"delivery_id": 42}, reason="max_retries_exceeded")

        mock_redis.lpush.assert_called_once()

        dlq_entry = json.loads(mock_redis.lpush.call_args[0][1])

        assert dlq_entry["delivery_id"] == 42
        assert dlq_entry["failed_reason"] == "max_retries_exceeded"


# ----------------------------
# Test 6 — Sanitizer
# ----------------------------

def test_sanitizer():

    from api.sanitizer import sanitize_payload

    payload = {
        "item": "book",
        "password": "secret",
        "token": "abc"
    }

    result = sanitize_payload(payload)

    assert "password" not in result
    assert "token" not in result
    assert result["item"] == "book"


# ----------------------------
# Test 7 — Rate Limit
# ----------------------------

def test_get_rate_limit(client):

    test_client, mock_redis = client

    mock_redis.get.return_value = None

    response = test_client.get("/internal/rate-limit")

    assert response.status_code == 200
    assert response.json()["rate_limit"] == 10


def test_update_rate_limit(client):

    test_client, mock_redis = client

    response = test_client.put(
        "/internal/rate-limit",
        json={"rate_limit": 25}
    )

    assert response.status_code == 200
    assert response.json()["rate_limit"] == 25

    mock_redis.set.assert_called_with("global_rate_limit", 25)
