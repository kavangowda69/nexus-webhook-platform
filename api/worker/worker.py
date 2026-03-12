import os
import json
import time
import requests
import redis

from sqlalchemy.orm import Session
from opentelemetry import trace
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from api.database.database import SessionLocal
from api.models.delivery import Delivery
from api.models.webhook import Webhook
from api.logger import get_logger
from api.metrics import DELIVERIES_SUCCESS, DELIVERIES_FAILED, DELIVERY_LATENCY
from api.tracing import setup_tracing


logger = get_logger("worker")
setup_tracing("webhook-worker")
RequestsInstrumentor().instrument()

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "webhook_redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

# ----------------------------
# Config
# ----------------------------
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_TIMEOUT = 60


# ----------------------------
# Circuit Breaker
# ----------------------------

def is_circuit_open(webhook_url: str) -> bool:
    key = f"circuit:{webhook_url}"
    failures = redis_client.get(key)
    if failures and int(failures) >= CIRCUIT_BREAKER_THRESHOLD:
        ttl = redis_client.ttl(key)
        logger.warning(
            f"circuit.open url={webhook_url} "
            f"failures={failures} ttl={ttl}s"
        )
        return True
    return False


def record_failure(webhook_url: str):
    key = f"circuit:{webhook_url}"
    failures = redis_client.incr(key)
    redis_client.expire(key, CIRCUIT_BREAKER_TIMEOUT)
    logger.warning(f"circuit.failure_recorded url={webhook_url} failures={failures}")


def reset_circuit(webhook_url: str):
    key = f"circuit:{webhook_url}"
    redis_client.delete(key)


# ----------------------------
# Dead Letter Queue
# ----------------------------

def send_to_dlq(job: dict, reason: str):
    dlq_entry = {**job, "failed_reason": reason}
    redis_client.lpush("webhook_dlq", json.dumps(dlq_entry))
    logger.error(
        f"dlq.sent delivery_id={job.get('delivery_id')} reason={reason}"
    )


# ----------------------------
# Delivery with Retry
# ----------------------------

def deliver_with_retry(webhook, delivery, delivery_id):
    tracer = trace.get_tracer("webhook-worker")

    for attempt in range(1, MAX_RETRIES + 1):
        with tracer.start_as_current_span(f"delivery_attempt_{attempt}") as span:
            span.set_attribute("delivery_id", delivery_id)
            span.set_attribute("webhook_id", webhook.id)
            span.set_attribute("attempt", attempt)
            span.set_attribute("webhook_url", webhook.url)

            try:
                start_time = time.time()

                response = requests.post(
                    webhook.url,
                    json={
                        "user_id": webhook.user_id,
                        "event_type": delivery.event_type,
                        "payload": delivery.payload
                    },
                    timeout=5
                )

                latency = time.time() - start_time
                DELIVERY_LATENCY.observe(latency)
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("latency_seconds", round(latency, 3))

                if 200 <= response.status_code < 300:
                    reset_circuit(webhook.url)
                    DELIVERIES_SUCCESS.labels(webhook_id=str(webhook.id)).inc()
                    logger.info(
                        f"delivery.success delivery_id={delivery_id} "
                        f"attempt={attempt} latency={latency:.3f}s"
                    )
                    return True
                else:
                    logger.warning(
                        f"delivery.attempt_failed delivery_id={delivery_id} "
                        f"attempt={attempt} status_code={response.status_code}"
                    )

            except Exception as e:
                latency = time.time() - start_time
                DELIVERY_LATENCY.observe(latency)
                span.record_exception(e)
                logger.error(
                    f"delivery.error delivery_id={delivery_id} "
                    f"attempt={attempt} error={str(e)}"
                )

            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY ** attempt
                logger.info(
                    f"delivery.retry_backoff delivery_id={delivery_id} "
                    f"attempt={attempt} wait={delay}s"
                )
                time.sleep(delay)

    record_failure(webhook.url)
    DELIVERIES_FAILED.labels(webhook_id=str(webhook.id)).inc()
    return False


# ----------------------------
# Process Job
# ----------------------------

def process_job(job_data):
    db: Session = SessionLocal()
    try:
        job = json.loads(job_data)
        delivery_id = job["delivery_id"]

        delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
        if not delivery:
            logger.warning(f"delivery.not_found delivery_id={delivery_id}")
            return

        webhook = db.query(Webhook).filter(Webhook.id == delivery.webhook_id).first()
        if not webhook:
            logger.warning(f"webhook.not_found webhook_id={delivery.webhook_id}")
            delivery.status = "failed"
            db.commit()
            return

        if is_circuit_open(webhook.url):
            logger.warning(
                f"delivery.circuit_open delivery_id={delivery_id} "
                f"url={webhook.url}"
            )
            send_to_dlq(job, reason="circuit_open")
            delivery.status = "failed"
            db.commit()
            return

        success = deliver_with_retry(webhook, delivery, delivery_id)

        if success:
            delivery.status = "success"
        else:
            delivery.status = "failed"
            send_to_dlq(job, reason="max_retries_exceeded")

        db.commit()

    finally:
        db.close()


# ----------------------------
# Worker Loop
# ----------------------------

def start_worker():
    logger.info("worker.started")

    last_second = int(time.time())
    processed_this_second = 0
    queue_index = 0

    while True:
        rate_limit = redis_client.get("global_rate_limit")
        RATE_LIMIT = int(rate_limit) if rate_limit else int(os.getenv("RATE_LIMIT", 10))

        now = int(time.time())
        if now != last_second:
            last_second = now
            processed_this_second = 0

        if processed_this_second >= RATE_LIMIT:
            time.sleep(0.05)
            continue

        queues = redis_client.keys("webhook_queue_*")
        if not queues:
            time.sleep(0.1)
            continue

        queue = queues[queue_index % len(queues)]
        queue_index += 1

        job = redis_client.rpop(queue)
        if job:
            process_job(job)
            processed_this_second += 1


if __name__ == "__main__":
    start_worker()
