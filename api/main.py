from fastapi import FastAPI, Request, Depends
from sqlalchemy.orm import Session

from api.database.database import Base, engine, SessionLocal
from api.models.webhook import Webhook

app = FastAPI()

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    
    payload = await request.json()

    event = Webhook(
        event_type=payload.get("event_type"),
        payload=str(payload)
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return {"message": "webhook received"}