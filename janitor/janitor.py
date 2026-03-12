import time
import json
import requests
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# ----------------------------
# Config
# ----------------------------
WATCH_INTERVAL = 10       # seconds between checks
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
NAMESPACE = "default"


# ----------------------------
# Kubernetes client setup
# ----------------------------

def get_k8s_client():
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client.CoreV1Api()


# ----------------------------
# Fetch crashed pods
# ----------------------------

def get_crashed_pods(v1):
    crashed = []
    pods = v1.list_namespaced_pod(namespace=NAMESPACE)
    for pod in pods.items:
        for cs in (pod.status.container_statuses or []):
            if cs.state.waiting and cs.state.waiting.reason in (
                "CrashLoopBackOff", "OOMKilled", "Error"
            ):
                crashed.append({
                    "pod_name": pod.metadata.name,
                    "reason": cs.state.waiting.reason,
                    "restart_count": cs.restart_count,
                })
    return crashed


# ----------------------------
# Fetch pod logs
# ----------------------------

def get_pod_logs(v1, pod_name: str) -> str:
    try:
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=NAMESPACE,
            tail_lines=50,
            previous=True
        )
        return logs
    except ApiException:
        try:
            logs = v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=NAMESPACE,
                tail_lines=50
            )
            return logs
        except ApiException as e:
            return f"Could not fetch logs: {e}"


# ----------------------------
# Ask LLM for diagnosis
# ----------------------------

def diagnose_with_llm(pod_name: str, reason: str, logs: str) -> str:
    prompt = f"""You are a Kubernetes expert.
A pod named '{pod_name}' has crashed with reason: {reason}

Here are the last 50 lines of logs:
{logs}

Provide:
1. Root cause (1-2 sentences)
2. Suggested fix (1-2 sentences)
Keep it concise and technical."""

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
        result = response.json()
        return result.get("response", "No diagnosis available")
    except Exception as e:
        return f"LLM unavailable: {str(e)}"


# ----------------------------
# Main loop
# ----------------------------

def run_janitor():
    print("Janitor started — watching for pod failures...")
    v1 = get_k8s_client()
    seen = set()

    while True:
        crashed_pods = get_crashed_pods(v1)

        for pod in crashed_pods:
            pod_name = pod["pod_name"]

            if pod_name in seen:
                continue

            seen.add(pod_name)

            print(f"\n{'='*60}")
            print(f"FAILURE DETECTED: {pod_name}")
            print(f"Reason: {pod['reason']} | Restarts: {pod['restart_count']}")
            print(f"{'='*60}")

            logs = get_pod_logs(v1, pod_name)
            diagnosis = diagnose_with_llm(pod_name, pod["reason"], logs)

            print(f"\nAI DIAGNOSIS:\n{diagnosis}")
            print(f"{'='*60}\n")

        time.sleep(WATCH_INTERVAL)


if __name__ == "__main__":
    run_janitor()