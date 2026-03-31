import logging

logger = logging.getLogger("aiops.planner")

CAUSE_ACTION_MAP = {
    "worker_saturation": "scale_workers",
    "worker": "scale_workers",
    "memory": "scale_workers",
    "queue": "scale_workers",
    "backlog": "scale_workers",
    "pod_crash": "restart_pod",
    "crash": "restart_pod",
    "oom": "restart_pod",
    "crashloopbackoff": "restart_pod",
    "db_latency": "alert_only",
    "database": "alert_only",
    "postgres": "alert_only",
    "redis": "alert_only",
    "network": "alert_only",
    "timeout": "alert_only",
}


def plan(incident, analysis):
    root_causes = analysis.get("root_causes", [])
    incident_type = incident.get("type", "")

    # Default action based on incident type
    if incident_type == "QUEUE_BACKLOG":
        default_action = "scale_workers"
    elif incident_type == "POD_CRASH":
        default_action = "restart_pod"
    elif incident_type == "HIGH_FAILURE_RATE":
        default_action = "alert_only"
    else:
        default_action = "alert_only"

    # Try to map from LLM root cause
    action = default_action
    best_confidence = 0.0

    for rc in root_causes:
        cause = rc.get("cause", "").lower()
        confidence = rc.get("confidence", 0.0)

        if confidence > best_confidence:
            for keyword, mapped_action in CAUSE_ACTION_MAP.items():
                if keyword in cause:
                    action = mapped_action
                    best_confidence = confidence
                    break

    plan_result = {
        "action": action,
        "incident_type": incident_type,
        "root_causes": root_causes,
        "explanation": analysis.get("explanation", ""),
        "confidence": best_confidence if best_confidence > 0 else 0.5,
        "pod_name": incident.get("pod_name")
    }

    logger.info(
        f"planner.plan_created action={action} "
        f"confidence={plan_result['confidence']:.2f}"
    )
    return plan_result