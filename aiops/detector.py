import logging
from aiops.prometheus_client import fetch_metrics
from aiops.kube_client import get_crashed_pods

logger = logging.getLogger("aiops.detector")

QUEUE_DEPTH_THRESHOLD = 5000
LATENCY_P95_THRESHOLD = 0.4   # 400ms in seconds
FAILURE_RATE_THRESHOLD = 0.1


def detect():
    incidents = []
    metrics = fetch_metrics()

    queue_depth = metrics.get("queue_depth", 0)
    latency_p95 = metrics.get("delivery_latency_p95", 0)
    failure_rate = metrics.get("delivery_failure_rate", 0)

    # Detect queue backlog
    if queue_depth > QUEUE_DEPTH_THRESHOLD and latency_p95 > LATENCY_P95_THRESHOLD:
        incident = {
            "type": "QUEUE_BACKLOG",
            "metrics": metrics,
            "severity": "HIGH",
            "description": (
                f"Queue depth {queue_depth} exceeds threshold {QUEUE_DEPTH_THRESHOLD} "
                f"and latency p95 {latency_p95:.3f}s exceeds {LATENCY_P95_THRESHOLD}s"
            )
        }
        logger.warning(f"detector.incident_detected type=QUEUE_BACKLOG "
                       f"queue_depth={queue_depth} latency_p95={latency_p95:.3f}")
        incidents.append(incident)

    # Detect high failure rate
    if failure_rate > FAILURE_RATE_THRESHOLD:
        incident = {
            "type": "HIGH_FAILURE_RATE",
            "metrics": metrics,
            "severity": "HIGH",
            "description": f"Delivery failure rate {failure_rate:.3f}/s exceeds threshold"
        }
        logger.warning(f"detector.incident_detected type=HIGH_FAILURE_RATE "
                       f"failure_rate={failure_rate:.3f}")
        incidents.append(incident)

    # Detect pod crashes
    crashed_pods = get_crashed_pods()
    for pod in crashed_pods:
        incident = {
            "type": "POD_CRASH",
            "pod_name": pod["pod_name"],
            "reason": pod["reason"],
            "restart_count": pod["restart_count"],
            "metrics": metrics,
            "severity": "CRITICAL",
            "description": (
                f"Pod {pod['pod_name']} in {pod['reason']} "
                f"with {pod['restart_count']} restarts"
            )
        }
        logger.warning(f"detector.incident_detected type=POD_CRASH "
                       f"pod={pod['pod_name']} reason={pod['reason']}")
        incidents.append(incident)

    if not incidents:
        logger.info("detector.no_incidents_detected")

    return incidents, metrics