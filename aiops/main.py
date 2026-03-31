import time
import logging
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiops.detector import detect
from aiops.analyzer import analyze
from aiops.planner import plan
from aiops.policy import evaluate
from aiops.executor import execute
from aiops.verifier import verify
from aiops.memory import init_db, store_incident

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "service": "aiops", '
           '"level": "%(levelname)s", "event": "%(message)s"}'
)

logger = logging.getLogger("aiops.main")

LOOP_INTERVAL = 30


def run_cycle():
    logger.info("aiops.cycle_start")

    # Step 1 — Detect
    incidents, metrics = detect()

    if not incidents:
        logger.info("aiops.cycle_complete status=no_incidents")
        return

    for incident in incidents:
        logger.info(
            f"aiops.processing_incident "
            f"type={incident.get('type')} "
            f"severity={incident.get('severity')}"
        )

        # Step 2 — Analyze
        analysis = analyze(incident, metrics)
        logger.info(
            f"aiops.analysis_complete "
            f"explanation={analysis.get('explanation', '')[:100]}"
        )

        # Step 3 — Plan
        action_plan = plan(incident, analysis)
        logger.info(f"aiops.plan action={action_plan.get('action')}")

        # Step 4 — Policy
        decision, approved_plan = evaluate(action_plan)
        logger.info(f"aiops.policy_decision decision={decision}")

        # Step 5 — Execute
        execution_result = execute(decision, approved_plan)
        logger.info(
            f"aiops.execution executed={execution_result.get('executed')} "
            f"reason={execution_result.get('reason', 'ok')}"
        )

        # Step 6 — Verify
        outcome = verify(execution_result, metrics)
        logger.info(f"aiops.verification outcome={outcome}")

        # Step 7 — Memory
        store_incident(incident, analysis, execution_result, outcome)

        logger.info(
            f"aiops.cycle_complete "
            f"type={incident.get('type')} "
            f"action={action_plan.get('action')} "
            f"outcome={outcome}"
        )


def main():
    logger.info("aiops.engine_starting")
    init_db()

    while True:
        try:
            run_cycle()
        except Exception as e:
            logger.error(f"aiops.cycle_error error={str(e)}")

        logger.info(f"aiops.sleeping seconds={LOOP_INTERVAL}")
        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    main()