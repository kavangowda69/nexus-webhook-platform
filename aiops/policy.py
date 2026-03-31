import logging
import time

logger = logging.getLogger("aiops.policy")

MAX_WORKER_PODS = 8
MIN_CONFIDENCE = 0.75
COOLDOWN_SECONDS = 300

_last_action_time = {}


def evaluate(plan):
    action = plan.get("action")
    confidence = plan.get("confidence", 0.0)

    # Check confidence threshold
    if confidence < MIN_CONFIDENCE:
        logger.warning(
            f"policy.reject reason=low_confidence "
            f"confidence={confidence:.2f} threshold={MIN_CONFIDENCE}"
        )
        return "REJECT", plan

    # Check cooldown
    now = time.time()
    last = _last_action_time.get(action, 0)
    if now - last < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - last))
        logger.warning(
            f"policy.reject reason=cooldown "
            f"action={action} cooldown_remaining={remaining}s"
        )
        return "REJECT", plan

    # Action-specific policy
    if action == "scale_workers":
        decision = "AUTO_EXECUTE"

    elif action == "restart_pod":
        decision = "REQUIRES_APPROVAL"

    elif action == "alert_only":
        decision = "AUTO_EXECUTE"

    else:
        decision = "REQUIRES_APPROVAL"

    logger.info(
        f"policy.decision decision={decision} "
        f"action={action} confidence={confidence:.2f}"
    )
    return decision, plan


def record_action(action):
    _last_action_time[action] = time.time()
    logger.info(f"policy.action_recorded action={action}")