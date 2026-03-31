import time
import logging
from aiops.prometheus_client import fetch_metrics

logger = logging.getLogger("aiops.verifier")

VERIFY_WAIT_SECONDS = 30
LATENCY_IMPROVEMENT_THRESHOLD = 0.1
QUEUE_IMPROVEMENT_THRESHOLD = 100


def verify(execution_result, metrics_before):
    if not execution_result.get("executed"):
        logger.info("verifier.skipped reason=nothing_executed")
        return "SKIPPED"

    logger.info(f"verifier.waiting seconds={VERIFY_WAIT_SECONDS}")
    time.sleep(VERIFY_WAIT_SECONDS)

    metrics_after = fetch_metrics()

    queue_before = metrics_before.get("queue_depth", 0)
    queue_after = metrics_after.get("queue_depth", 0)
    latency_before = metrics_before.get("delivery_latency_p95", 0)
    latency_after = metrics_after.get("delivery_latency_p95", 0)
    failure_before = metrics_before.get("delivery_failure_rate", 0)
    failure_after = metrics_after.get("delivery_failure_rate", 0)

    queue_improved = (queue_before - queue_after) > QUEUE_IMPROVEMENT_THRESHOLD
    latency_improved = (latency_before - latency_after) > LATENCY_IMPROVEMENT_THRESHOLD
    failure_improved = failure_after <= failure_before

    logger.info(
        f"verifier.comparison "
        f"queue_before={queue_before} queue_after={queue_after} "
        f"latency_before={latency_before:.3f} latency_after={latency_after:.3f} "
        f"failure_before={failure_before:.3f} failure_after={failure_after:.3f}"
    )

    if queue_improved or latency_improved or failure_improved:
        logger.info("verifier.outcome=RESOLVED")
        return "RESOLVED"
    else:
        logger.warning("verifier.outcome=ESCALATE")
        return "ESCALATE"