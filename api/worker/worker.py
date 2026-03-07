import json
import requests
import redis

from sqlalchemy.orm import Session
from api.database.database import SessionLocal
from api.models.delivery import Delivery
from api.models.webhook import Webhook

redis_client = redis.Redis(host="webhook_redis", port=6379, db=0)

def process_job(job_data):

    db: Session = SessionLocal()

    try:
        job = json.loads(job_data)

        delivery_id = job["delivery_id"]

        delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()

        if not delivery:
            return

        webhook = db.query(Webhook).filter(Webhook.id == delivery.webhook_id).first()

        if not webhook:
            delivery.status = "failed"
            db.commit()
            return

        try:

            response = requests.post(
                webhook.url,
                json={
                    "event_type": delivery.event_type,
                    "payload": delivery.payload
                },
                timeout=5
            )

            if 200 <= response.status_code < 300:
                delivery.status = "success"
            else:
                delivery.status = "failed"

        except Exception as e:
            print("Delivery error:", e)
            delivery.status = "failed"

        db.commit()

    finally:
        db.close()


def start_worker():

    print("Redis Worker started...")

    while True:

        job = redis_client.brpop("webhook_queue")

        if job:
            _, job_data = job
            process_job(job_data)


if __name__ == "__main__":
    start_worker()