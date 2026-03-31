import requests
import logging
import os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("aiops.elk_client")

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")


def fetch_recent_logs(minutes=2, size=50):
    try:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        since_str = since.isoformat()

        query = {
            "size": size,
            "sort": [{"timestamp": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": [
                        {"range": {"timestamp": {"gte": since_str}}}
                    ]
                }
            }
        }

        response = requests.post(
            f"{ELASTICSEARCH_URL}/nexus-*/_search",
            json=query,
            timeout=5
        )

        hits = response.json().get("hits", {}).get("hits", [])
        logs = [hit["_source"] for hit in hits]
        logger.info(f"elk_client.fetch_logs count={len(logs)}")
        return logs

    except Exception as e:
        logger.error(f"elk_client.fetch_recent_logs error={str(e)}")
        return []


def fetch_error_logs(minutes=2):
    try:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        since_str = since.isoformat()

        query = {
            "size": 20,
            "sort": [{"timestamp": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": [
                        {"range": {"timestamp": {"gte": since_str}}},
                        {"terms": {"level": ["ERROR", "WARNING"]}}
                    ]
                }
            }
        }

        response = requests.post(
            f"{ELASTICSEARCH_URL}/nexus-*/_search",
            json=query,
            timeout=5
        )

        hits = response.json().get("hits", {}).get("hits", [])
        logs = [hit["_source"] for hit in hits]
        logger.info(f"elk_client.fetch_error_logs count={len(logs)}")
        return logs

    except Exception as e:
        logger.error(f"elk_client.fetch_error_logs error={str(e)}")
        return []