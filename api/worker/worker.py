import os
import json
import time
import requests
import redis

from sqlalchemy.orm import Session
from api.database.database import SessionLocal
from api.models.delivery import Delivery
from api.models.webhook import Webhook
from api.logger import get_logger
from api.metrics import DELIVERIES_SUCCESS, DELIVERIES_FAILED, DELIVERY_LATENCY
from prometheus_client import start_http_server

logger = get_logger("worker")

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "webhook_redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)


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

            if 200 <= response.status_code < 300:
                delivery.status = "success"
                DELIVERIES_SUCCESS.labels(webhook_id=str(webhook.id)).inc()
                logger.info(f"delivery.success delivery_id={delivery_id} webhook_id={webhook.id} status_code={response.status_code} latency={latency:.3f}s")
            else:
                delivery.status = "failed"
                DELIVERIES_FAILED.labels(webhook_id=str(webhook.id)).inc()
                logger.warning(f"delivery.failed delivery_id={delivery_id} status_code={response.status_code}")

        except Exception as e:
            latency = time.time() - start_time
            DELIVERY_LATENCY.observe(latency)
            DELIVERIES_FAILED.labels(webhook_id=str(webhook.id)).inc()
            logger.error(f"delivery.error delivery_id={delivery_id} error={str(e)}")
            delivery.status = "failed"

        db.commit()

    finally:
        db.close()


def start_worker():
    start_http_server(9090)  # worker metrics on port 9090
    logger.info("worker.started metrics_port=9090")

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