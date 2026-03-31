import logging
import os
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

logger = logging.getLogger("aiops.memory")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://webhook_user:webhook_pass@localhost:5432/webhook_db"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Incident(Base):
    __tablename__ = "aiops_incidents"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    incident_type = Column(String)
    cause = Column(Text)
    action = Column(String)
    outcome = Column(String)
    explanation = Column(Text)
    metrics_snapshot = Column(Text)


def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("memory.db_initialized")
    except Exception as e:
        logger.error(f"memory.init_error error={str(e)}")


def store_incident(incident, analysis, execution_result, outcome):
    db = SessionLocal()
    try:
        causes = analysis.get("root_causes", [])
        cause_str = json.dumps(causes)
        action = execution_result.get("action", "none")
        metrics = incident.get("metrics", {})

        record = Incident(
            incident_type=incident.get("type", "unknown"),
            cause=cause_str,
            action=action,
            outcome=outcome,
            explanation=analysis.get("explanation", ""),
            metrics_snapshot=json.dumps(metrics)
        )

        db.add(record)
        db.commit()
        logger.info(
            f"memory.stored incident_type={incident.get('type')} "
            f"action={action} outcome={outcome}"
        )

    except Exception as e:
        logger.error(f"memory.store_error error={str(e)}")
        db.rollback()
    finally:
        db.close()


def get_recent_incidents(limit=10):
    db = SessionLocal()
    try:
        incidents = db.query(Incident)\
            .order_by(Incident.timestamp.desc())\
            .limit(limit)\
            .all()
        return incidents
    except Exception as e:
        logger.error(f"memory.get_error error={str(e)}")
        return []
    finally:
        db.close()