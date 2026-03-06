from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.database.database import Base


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)

    webhook_id = Column(Integer, ForeignKey("webhooks.id"))

    event_type = Column(String, index=True)

    payload = Column(Text)

    status = Column(String, default="pending")  
    # pending | success | failed

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    webhook = relationship("Webhook")