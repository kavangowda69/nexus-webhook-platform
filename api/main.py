from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from api.database.database import SessionLocal, engine
from api.models.webhook import Webhook, Base
from api.models.delivery import Delivery

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)


# Dependency
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

    return webhook


@app.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: int, db: Session = Depends(get_db)):

    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    db.delete(webhook)
    db.commit()

    return {"message": "Webhook deleted"}


@app.patch("/webhooks/{webhook_id}/disable")
def disable_webhook(webhook_id: int, db: Session = Depends(get_db)):

    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook.active = False
    db.commit()

    return {"message": "Webhook disabled"}


@app.patch("/webhooks/{webhook_id}/enable")
def enable_webhook(webhook_id: int, db: Session = Depends(get_db)):

    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook.active = True
    db.commit()

    return {"message": "Webhook enabled"}


# ----------------------------
# Event Ingestion
# ----------------------------

@app.post("/events")
def publish_event(event: EventCreate, db: Session = Depends(get_db)):

    webhooks = db.query(Webhook).filter(
        Webhook.user_id == event.user_id,
        Webhook.active == True
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
            deliveries_created += 1

    db.commit()

    return {
        "message": "Event accepted",
        "deliveries_created": deliveries_created
    }