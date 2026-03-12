import logging
import json
import os
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def __init__(self, service_name):
        super().__init__()
        self.service_name = service_name

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.service_name,
            "level": record.levelname,
            "event": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def get_logger(service_name: str) -> logging.Logger:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter(service_name))
        logger.addHandler(handler)

    return logger