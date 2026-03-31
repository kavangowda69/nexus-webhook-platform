import requests
import json
import logging
import os
from aiops.elk_client import fetch_error_logs
from aiops.kube_client import get_pod_logs

logger = logging.getLogger("aiops.analyzer")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")


def call_llm(prompt):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        return response.json().get("response", "")
    except Exception as e:
        logger.error(f"analyzer.llm_error error={str(e)}")
        return ""


def analyze(incident, metrics):
    error_logs = fetch_error_logs(minutes=2)

    log_text = "\n".join([
        f"[{log.get('level', 'INFO')}] {log.get('event', '')}"
        for log in error_logs[:20]
    ])

    pod_logs = ""
    if incident.get("type") == "POD_CRASH" and incident.get("pod_name"):
        pod_logs = get_pod_logs(incident["pod_name"])

    prompt = f"""You are a Kubernetes and distributed systems expert performing root cause analysis.

Incident Type: {incident.get('type')}
Description: {incident.get('description')}
Severity: {incident.get('severity')}

Current System Metrics:
- Queue Depth: {metrics.get('queue_depth', 0)}
- Delivery Latency p95: {metrics.get('delivery_latency_p95', 0):.3f}s
- Delivery Failure Rate: {metrics.get('delivery_failure_rate', 0):.3f}/s
- Delivery Success Rate: {metrics.get('delivery_success_rate', 0):.3f}/s

Recent Error Logs (last 2 minutes):
{log_text if log_text else 'No recent error logs'}

{f'Pod Logs:{chr(10)}{pod_logs}' if pod_logs else ''}

Respond ONLY with a JSON object in this exact format with no other text:
{{
  "root_causes": [
    {{"cause": "cause description", "confidence": 0.85}}
  ],
  "explanation": "brief explanation of what is happening and why"
}}"""

    raw = call_llm(prompt)

    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            result = json.loads(raw[start:end])
            logger.info(
                f"analyzer.analysis_complete "
                f"causes={len(result.get('root_causes', []))}"
            )
            return result
    except Exception as e:
        logger.error(f"analyzer.parse_error error={str(e)}")

    return {
        "root_causes": [{"cause": "unknown", "confidence": 0.0}],
        "explanation": "LLM analysis unavailable"
    }