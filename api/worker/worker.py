import ast
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

INFERENCE_SERVER_URL = os.getenv("INFERENCE_SERVER_URL", "http://inference_server:3001")

# ----------------------------
# Config
# ----------------------------
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_TIMEOUT = 60

# Adaptive rate limiting config
RATE_INCREASE_STEP = 1
RATE_DECREASE_STEP = 2
RATE_MIN = 1
RATE_MAX = 50


# ----------------------------
# Adaptive Rate Limiter
# ----------------------------

def get_endpoint_rate(webhook_url: str) -> int:
    key = f"adaptive_rate:{webhook_url}"
    rate = redis_client.get(key)
    if rate is None:
        default = int(os.getenv("RATE_LIMIT", 10))
        redis_client.set(key, default)
        return default
    return int(rate)


def increase_rate(webhook_url: str):
    key = f"adaptive_rate:{webhook_url}"
    current = get_endpoint_rate(webhook_url)
    new_rate = min(current + RATE_INCREASE_STEP, RATE_MAX)
    redis_client.set(key, new_rate)
    if new_rate != current:
        logger.info(
            f"adaptive_rate.increased url={webhook_url} "
            f"old={current} new={new_rate}"
        )


def decrease_rate(webhook_url: str):
    key = f"adaptive_rate:{webhook_url}"
    current = get_endpoint_rate(webhook_url)
    new_rate = max(current - RATE_DECREASE_STEP, RATE_MIN)
    redis_client.set(key, new_rate)
    if new_rate != current:
        logger.warning(
            f"adaptive_rate.decreased url={webhook_url} "
            f"old={current} new={new_rate}"
        )


def compute_endpoint_score(webhook_url: str) -> float:
    success_key = f"endpoint_success:{webhook_url}"
    total_key = f"endpoint_total:{webhook_url}"
    latency_key = f"endpoint_latency:{webhook_url}"

    success = int(redis_client.get(success_key) or 0)
    total = int(redis_client.get(total_key) or 1)
    avg_latency = float(redis_client.get(latency_key) or 0.5)

    success_rate = success / total
    latency_factor = max(0.1, 1.0 - (avg_latency / 5.0))
    score = success_rate * latency_factor

    logger.info(
        f"endpoint.score url={webhook_url} score={score:.2f} "
        f"success_rate={success_rate:.2f} latency_factor={latency_factor:.2f}"
    )
    return score


def record_endpoint_result(webhook_url: str, success: bool, latency: float):
    total_key = f"endpoint_total:{webhook_url}"
    success_key = f"endpoint_success:{webhook_url}"
    latency_key = f"endpoint_latency:{webhook_url}"

    redis_client.incr(total_key)
    redis_client.expire(total_key, 300)

    if success:
        redis_client.incr(success_key)
        redis_client.expire(success_key, 300)

    redis_client.set(latency_key, round(latency, 3))
    redis_client.expire(latency_key, 300)


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
    logger.warning(
        f"circuit.failure_recorded url={webhook_url} failures={failures}"
    )


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
# Inference Routing
# ----------------------------

def route_to_inference(delivery, webhook, delivery_id):
    tracer = trace.get_tracer("webhook-worker")

    with tracer.start_as_current_span("inference.request") as span:
        span.set_attribute("delivery_id", delivery_id)
        span.set_attribute("webhook_id", webhook.id)

        try:
            payload = ast.literal_eval(delivery.payload)
        except Exception:
            payload = {"input": delivery.payload}

        try:
            response = requests.post(
                f"{INFERENCE_SERVER_URL}/predict",
                json={
                    "request": {
                        "input": payload,
                        "model": payload.get("model", "echo")
                    }
                },
                timeout=30
            )

            if response.status_code == 200:
                prediction = response.json()
                logger.info(
                    f"inference.success delivery_id={delivery_id} "
                    f"model={payload.get('model', 'echo')}"
                )

                requests.post(
                    webhook.url,
                    json={
                        "user_id": webhook.user_id,
                        "event_type": "inference.completed",
                        "prediction": prediction
                    },
                    timeout=5
                )
                return True
            else:
                logger.warning(
                    f"inference.failed delivery_id={delivery_id} "
                    f"status={response.status_code}"
                )
                return False

        except Exception as e:
            span.record_exception(e)
            logger.error(f"inference.error delivery_id={delivery_id} error={str(e)}")
            return False


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

                record_endpoint_result(webhook.url, True, latency)

                if 200 <= response.status_code < 300:
                    reset_circuit(webhook.url)
                    increase_rate(webhook.url)
                    DELIVERIES_SUCCESS.labels(webhook_id=str(webhook.id)).inc()
                    logger.info(
                        f"delivery.success delivery_id={delivery_id} "
                        f"attempt={attempt} latency={latency:.3f}s"
                    )
                    return True
                elif response.status_code in (429, 503):
                    record_endpoint_result(webhook.url, False, latency)
                    decrease_rate(webhook.url)
                    logger.warning(
                        f"delivery.throttled delivery_id={delivery_id} "
                        f"status_code={response.status_code} "
                        f"rate decreased for url={webhook.url}"
                    )
                else:
                    record_endpoint_result(webhook.url, False, latency)
                    logger.warning(
                        f"delivery.attempt_failed delivery_id={delivery_id} "
                        f"attempt={attempt} status_code={response.status_code}"
                    )

            except Exception as e:
                latency = time.time() - start_time
                DELIVERY_LATENCY.observe(latency)
                record_endpoint_result(webhook.url, False, latency)
                decrease_rate(webhook.url)
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

        # Route inference events to model server
        if delivery.event_type == "inference.requested":
            logger.info(f"inference.routing delivery_id={delivery_id}")
            success = route_to_inference(delivery, webhook, delivery_id)
            delivery.status = "success" if success else "failed"
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

        score = compute_endpoint_score(webhook.url)
        if score < 0.5:
            decrease_rate(webhook.url)
        else:
            increase_rate(webhook.url)

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
        now = int(time.time())
        if now != last_second:
            last_second = now
            processed_this_second = 0

        global_limit = redis_client.get("global_rate_limit")
        RATE_LIMIT = int(global_limit) if global_limit else int(os.getenv("RATE_LIMIT", 10))

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
