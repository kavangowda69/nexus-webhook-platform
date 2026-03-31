import logging
import json
import os
import socket
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

        # Add error_type for AIOps analyzer
        msg = record.getMessage().lower()
        if "timeout" in msg:
            log_entry["error_type"] = "timeout"
        elif "crash" in msg or "crashloop" in msg:
            log_entry["error_type"] = "crash"
        elif "retry" in msg:
            log_entry["error_type"] = "retry"
        elif "oom" in msg or "memory" in msg:
            log_entry["error_type"] = "oom"
        elif "connection" in msg:
            log_entry["error_type"] = "connection"
        elif record.levelname == "ERROR":
            log_entry["error_type"] = "error"

        # Add trace_id if available
        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            log_entry["trace_id"] = trace_id

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class UDPLogstashHandler(logging.Handler):
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.sock.sendto(msg.encode("utf-8"), (self.host, self.port))
        except Exception:
            pass


def get_logger(service_name: str) -> logging.Logger:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(JSONFormatter(service_name))
        logger.addHandler(console_handler)

        logstash_host = os.getenv("LOGSTASH_HOST", "logstash")
        logstash_port = int(os.getenv("LOGSTASH_PORT", 5000))
        udp_handler = UDPLogstashHandler(logstash_host, logstash_port)
        udp_handler.setFormatter(JSONFormatter(service_name))
        logger.addHandler(udp_handler)

    return logger
