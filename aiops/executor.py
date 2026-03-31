import logging
import subprocess
import time
from aiops.policy import record_action

logger = logging.getLogger("aiops.executor")

HPA_NAME = "webhook-worker"

SCALE_UP_BY = 1
MAX_LIMIT = 8
COOLDOWN_SECONDS = 300

LAST_ACTION_TIME = 0


def get_current_hpa_max():
    try:
        result = subprocess.run(
            [
                "kubectl", "get", "hpa", HPA_NAME,
                "-o", "jsonpath={.spec.maxReplicas}"
            ],
            capture_output=True,
            text=True
        )
        return int(result.stdout.strip())
    except Exception as e:
        logger.error(f"executor.hpa_read_failed error={e}")
        return None


def patch_hpa_max(new_max):
    try:
        subprocess.run(
            [
                "kubectl", "patch", "hpa", HPA_NAME,
                "-p", f'{{"spec":{{"maxReplicas":{new_max}}}}}'
            ],
            check=True
        )
        return True
    except Exception as e:
        logger.error(f"executor.hpa_patch_failed error={e}")
        return False


def execute(decision, plan):
    global LAST_ACTION_TIME

    action = plan.get("action")
    now = time.time()

    # 🔒 POLICY HANDLING
    if decision == "REJECT":
        logger.info(f"executor.skipped reason=policy_rejected action={action}")
        return {"executed": False, "reason": "policy_rejected"}

    if decision == "REQUIRES_APPROVAL":
        logger.warning(
            f"executor.approval_required action={action} "
            f"explanation={plan.get('explanation', '')}"
        )
        return {"executed": False, "reason": "requires_approval", "action": action}

    # ⏳ COOLDOWN CHECK
    if now - LAST_ACTION_TIME < COOLDOWN_SECONDS:
        logger.warning("executor.cooldown_active skipping_action")
        return {"executed": False, "reason": "cooldown_active"}

    # 🚀 SCALE VIA HPA (CORRECT APPROACH)
    if action == "scale_workers":
        current_max = get_current_hpa_max()

        if current_max is None:
            return {"executed": False, "reason": "hpa_read_failed"}

        new_max = min(current_max + SCALE_UP_BY, MAX_LIMIT)

        if new_max == current_max:
            logger.warning(
                f"executor.scale_skipped reason=already_at_max max={current_max}"
            )
            return {"executed": False, "reason": "already_at_max"}

        success = patch_hpa_max(new_max)

        if success:
            LAST_ACTION_TIME = now
            record_action(action)

            logger.info(
                f"executor.hpa_scaled name={HPA_NAME} "
                f"from_max={current_max} to_max={new_max}"
            )

            return {
                "executed": True,
                "action": action,
                "old_max": current_max,
                "new_max": new_max
            }
        else:
            return {"executed": False, "reason": "hpa_patch_failed"}

    # 🔔 ALERT ONLY
    elif action == "alert_only":
        logger.warning(
            f"executor.alert_only "
            f"explanation={plan.get('explanation', '')} "
            f"causes={plan.get('root_causes', [])}"
        )
        record_action(action)

        return {"executed": True, "action": "alert_only"}

    # ❓ UNKNOWN ACTION
    logger.error(f"executor.unknown_action action={action}")
    return {"executed": False, "reason": "unknown_action"}