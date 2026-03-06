from sqlalchemy import Column, Integer, String, Text
from api.database.database import Base

class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String)
    payload = Column(Text)