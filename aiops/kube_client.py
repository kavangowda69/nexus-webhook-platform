import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger("aiops.kube_client")


def get_k8s_client():
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client.CoreV1Api(), client.AppsV1Api()


def get_crashed_pods(namespace="default"):
    crashed = []
    try:
        v1, _ = get_k8s_client()
        pods = v1.list_namespaced_pod(namespace=namespace)
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
    except Exception as e:
        logger.error(f"kube_client.get_crashed_pods error={str(e)}")
    return crashed


def get_pod_logs(pod_name, namespace="default", tail=50):
    try:
        v1, _ = get_k8s_client()
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail,
            previous=True
        )
        return logs
    except ApiException:
        try:
            v1, _ = get_k8s_client()
            logs = v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=tail
            )
            return logs
        except Exception as e:
            logger.error(f"kube_client.get_pod_logs error={str(e)}")
            return ""
    except Exception as e:
        logger.error(f"kube_client.get_pod_logs error={str(e)}")
        return ""


def scale_deployment(deployment, replicas, namespace="default"):
    try:
        _, apps_v1 = get_k8s_client()
        body = {"spec": {"replicas": replicas}}
        apps_v1.patch_namespaced_deployment_scale(
            name=deployment,
            namespace=namespace,
            body=body
        )
        logger.info(
            f"kube_client.scale deployment={deployment} replicas={replicas}"
        )
        return True
    except Exception as e:
        logger.error(f"kube_client.scale error={str(e)}")
        return False


def get_deployment_replicas(deployment, namespace="default"):
    try:
        _, apps_v1 = get_k8s_client()
        d = apps_v1.read_namespaced_deployment(
            name=deployment,
            namespace=namespace
        )
        return d.spec.replicas
    except Exception as e:
        logger.error(f"kube_client.get_replicas error={str(e)}")
        return None