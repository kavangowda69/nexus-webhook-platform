import os
import redis
import json

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from prometheus_client import generate_latest, REGISTRY, CONTENT_TYPE_LATEST

from api.database.database import SessionLocal, engine
from api.models.webhook import Webhook, Base
from api.models.delivery import Delivery
from api.logger import get_logger
from api.metrics import EVENTS_RECEIVED, QUEUE_DEPTH

logger = get_logger("api")

app = FastAPI()

Base.metadata.create_all(bind=engine)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "webhook_redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------
# Schemas
# ----------------------------

class WebhookCreate(BaseModel):
    user_id: str
    url: str
    event_types: List[str]


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    event_types: Optional[List[str]] = None


class EventCreate(BaseModel):
    user_id: str
    event_type: str
    payload: dict


class RateLimitUpdate(BaseModel):
    rate_limit: int


# ----------------------------
# Health
# ----------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# ----------------------------
# Metrics
# ----------------------------

@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )


# ----------------------------
# Rate Limit API
# ----------------------------

@app.get("/internal/rate-limit")
def get_rate_limit():
    rate = redis_client.get("global_rate_limit")
    if rate is None:
        return {"rate_limit": 10}
    return {"rate_limit": int(rate)}


@app.put("/internal/rate-limit")
def update_rate_limit(data: RateLimitUpdate):
    redis_client.set("global_rate_limit", data.rate_limit)
    logger.info(f"rate_limit.updated limit={data.rate_limit}")
    return {"rate_limit": data.rate_limit}


# ----------------------------
# Webhook CRUD
# ----------------------------

@app.post("/webhooks")
def register_webhook(webhook: WebhookCreate, db: Session = Depends(get_db)):
    new_webhook = Webhook(
        user_id=webhook.user_id,
        url=webhook.url,
        event_types=webhook.event_types,
        active=True
    )
    db.add(new_webhook)
    db.commit()
    db.refresh(new_webhook)
    logger.info(f"webhook.registered webhook_id={new_webhook.id} user_id={webhook.user_id}")
    return new_webhook


@app.get("/webhooks")
def list_webhooks(db: Session = Depends(get_db)):
    return db.query(Webhook).all()


@app.put("/webhooks/{webhook_id}")
def update_webhook(webhook_id: int, update_data: WebhookUpdate, db: Session = Depends(get_db)):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if update_data.url is not None:
        webhook.url = update_data.url
    if update_data.event_types is not None:
        webhook.event_types = update_data.event_types
    db.commit()
    db.refresh(webhook)
    logger.info(f"webhook.updated webhook_id={webhook_id}")
    return webhook


@app.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: int, db: Session = Depends(get_db)):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.delete(webhook)
    db.commit()
    logger.info(f"webhook.deleted webhook_id={webhook_id}")
    return {"message": "Webhook deleted"}


@app.patch("/webhooks/{webhook_id}/disable")
def disable_webhook(webhook_id: int, db: Session = Depends(get_db)):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    webhook.active = False
    db.commit()
    logger.info(f"webhook.disabled webhook_id={webhook_id}")
    return {"message": "Webhook disabled"}


@app.patch("/webhooks/{webhook_id}/enable")
def enable_webhook(webhook_id: int, db: Session = Depends(get_db)):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    webhook.active = True
    db.commit()
    logger.info(f"webhook.enabled webhook_id={webhook_id}")
    return {"message": "Webhook enabled"}


# ----------------------------
# Event Ingestion
# ----------------------------

@app.post("/events")
def publish_event(event: EventCreate, db: Session = Depends(get_db)):
    logger.info(f"event.received user_id={event.user_id} event_type={event.event_type}")

    webhooks = db.query(Webhook).filter(
        Webhook.user_id == event.user_id,
        Webhook.active == True  # noqa: E712
    ).all()

    deliveries_created = 0

    for webhook in webhooks:
        if event.event_type in webhook.event_types:
            delivery = Delivery(
                webhook_id=webhook.id,
                event_type=event.event_type,
                payload=str(event.payload),
                status="pending"
            )
            db.add(delivery)
            db.flush()

            queue_name = f"webhook_queue_{event.user_id}"
            redis_client.lpush(
                queue_name,
                json.dumps({"delivery_id": delivery.id})
            )
            deliveries_created += 1

    db.commit()

    EVENTS_RECEIVED.labels(
        user_id=event.user_id,
        event_type=event.event_type
    ).inc(deliveries_created)

    total_depth = redis_client.llen(f"webhook_queue_{event.user_id}")
    QUEUE_DEPTH.set(total_depth)

    logger.info(f"event.queued user_id={event.user_id} deliveries_created={deliveries_created}")
    return {
        "message": "Event accepted",
        "deliveries_created": deliveries_created
    }
