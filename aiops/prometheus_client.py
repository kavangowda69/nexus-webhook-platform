import requests
import logging
import os

logger = logging.getLogger("aiops.prometheus_client")

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9091")

def query(promql):
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": promql},
            timeout=5
        )
        data = response.json()
        results = data.get("data", {}).get("result", [])
        if results:
            return float(results[0]["value"][1])
        return 0.0
    except Exception as e:
        logger.error(f"prometheus_client.query promql={promql} error={str(e)}")
        return 0.0


def query_all(promql):
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": promql},
            timeout=5
        )
        data = response.json()
        return data.get("data", {}).get("result", [])
    except Exception as e:
        logger.error(f"prometheus_client.query_all error={str(e)}")
        return []


def fetch_metrics():
    metrics = {
        "queue_depth": query("webhook_queue_depth"),
        "delivery_failure_rate": query(
            "rate(webhook_delivery_failed_total[5m])"
        ),
        "delivery_latency_p95": query(
            "histogram_quantile(0.95, rate(webhook_delivery_latency_seconds_bucket[5m]))"
        ),
        "delivery_success_rate": query(
            "rate(webhook_delivery_success_total[5m])"
        ),
    }
    logger.info(f"prometheus_client.metrics fetched metrics={metrics}")
    return metrics