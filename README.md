# Nexus — Autonomous Webhook Delivery Platform

A production-grade distributed webhook delivery system that evolved from a basic event processor into a self-healing, self-analyzing platform with autonomous incident remediation, ML inference routing, and a full DevSecOps pipeline.

Built phase by phase — every component exists for a reason, every decision is documented, every service has been deployed and verified on real infrastructure.

## 2-Minute System Demo:
https://www.loom.com/share/61abc5b856eb40ec817bfc782c3cc147
---

## What it does

Clients register webhooks and publish events. Nexus queues deliveries per user with fairness scheduling, routes them to endpoints with retry and exponential backoff, adapts delivery rate based on real-time endpoint health, and recovers automatically from failures using circuit breaking and dead letter queues.

While all this runs, an autonomous AIOps engine watches the entire system — detecting anomalies in Prometheus metrics, analyzing root causes using LLM intelligence, planning remediation actions, enforcing safety policies, executing fixes, verifying outcomes, and storing institutional memory in Postgres. When the system detects a problem it solves it. When it can't solve it safely, it escalates to a human with a full diagnosis already written.
```
Client → POST /events
           │
           ▼
       FastAPI API ──→ Payload Sanitization
           │
       Redis Queue (per-user, round-robin fairness)
           │
       Worker Cluster (2–5 pods, HPA autoscaled)
           │         │
           │         └──→ inference.requested → BentoML Model Server → prediction callback
           │
       Webhook Endpoint
           │
       ┌───────────────────────────────────┐
       │         AIOps Engine              │
       │  Detect → Analyze → Plan →        │
       │  Policy → Execute → Verify →      │
       │  Memory (every 30 seconds)        │
       └───────────────────────────────────┘
```

---

## Tech stack

| Layer | Tools |
|---|---|
| API | FastAPI, SQLAlchemy, Postgres |
| Queue | Redis |
| Containers | Docker (multi-stage, 341MB images) |
| Orchestration | Kubernetes, Helm, HPA |
| GitOps | ArgoCD |
| Cloud | AWS EKS, ECR, VPC, IAM |
| IaC | Terraform |
| Observability | Prometheus, Grafana, Jaeger (OpenTelemetry) |
| Log Aggregation | Elasticsearch, Logstash, Kibana |
| Alerting | AlertManager, Slack |
| AIOps | Kubernetes Python client, Ollama, Llama 3, Prometheus API, ELK API |
| CI/CD | GitHub Actions, GitHub Container Registry |
| Security | Trivy container scanning, payload sanitization |
| ML Inference | BentoML |
| Load testing | k6 |

---

## Architecture
```
                        ┌──────────────────────────────────────────┐
                        │       Kubernetes Cluster                  │
                        │       (minikube / AWS EKS)                │
                        │                                          │
  Client                │  ┌──────────┐    ┌───────────────┐      │
    │                   │  │   API    │    │    Worker     │      │
    │ POST /events       │  │  (pods)  │    │  (2–5 pods)   │      │
    └──────────────────▶│  └────┬─────┘    └──────┬────────┘      │
                        │       │                  │               │
                        │       ▼                  ▼               │
                        │  ┌─────────┐    ┌──────────────┐        │
                        │  │  Redis  │───▶│   Postgres   │        │
                        │  └─────────┘    └──────────────┘        │
                        │                                          │
                        │  ┌────────────────────────────────────┐  │
                        │  │           AIOps Engine             │  │
                        │  │  Every 30s:                        │  │
                        │  │  Prometheus → detect anomalies     │  │
                        │  │  ELK → fetch error logs            │  │
                        │  │  Ollama/Llama3 → root cause        │  │
                        │  │  Planner → map to action           │  │
                        │  │  Policy → enforce safety gates     │  │
                        │  │  Executor → scale/restart/alert    │  │
                        │  │  Verifier → confirm resolution     │  │
                        │  │  Memory → store in Postgres        │  │
                        │  └────────────────────────────────────┘  │
                        └──────────────────────────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
         Prometheus               Grafana                    Jaeger
         (metrics)               (dashboards)               (traces)
              │
         AlertManager → Slack

  GitOps: git push → CI → GHCR → ArgoCD → Kubernetes
  Cloud:  Terraform → VPC + EKS + ECR (ap-south-1, verified)
  Logs:   API/Worker → Logstash UDP → Elasticsearch → Kibana
```

---

## AIOps Engine

The most advanced component. A fully autonomous Detect → Analyze → Plan → Policy → Execute → Verify → Memory loop running every 30 seconds inside Kubernetes.

### What it detects
- `POD_CRASH` — CrashLoopBackOff, OOMKilled, Error states via Kubernetes Python client
- `QUEUE_BACKLOG` — queue depth > 5000 AND latency p95 > 400ms simultaneously
- `HIGH_FAILURE_RATE` — delivery failure rate exceeding threshold

### How it works
```
1. DETECT    — Kubernetes Python client scans pod states
               Prometheus API fetches queue_depth, latency_p95, failure_rate

2. ANALYZE   — ELK fetches last 2 minutes of ERROR/WARNING logs
               Ollama/Llama3 receives structured prompt with metrics + logs
               Returns: { root_causes: [{cause, confidence}], explanation }

3. PLAN      — Maps root causes to actions:
               worker_saturation → scale_workers
               pod_crash         → restart_pod
               db_latency        → alert_only

4. POLICY    — Safety gates before any action:
               min_confidence = 0.75 (rejects low-confidence actions)
               cooldown = 300s (prevents action storms)
               max_worker_pods = 8

5. EXECUTE   — AUTO_EXECUTE: scales deployment via Kubernetes API
               REQUIRES_APPROVAL: logs for human review
               REJECT: skips with reason logged

6. VERIFY    — Waits 30s, re-fetches metrics
               Checks if queue ↓, latency ↓, failures ↓
               Returns RESOLVED or ESCALATE

7. MEMORY    — Stores every incident in Postgres:
               (id, timestamp, incident_type, cause, action, outcome)
               Builds institutional knowledge over time
```

### What reaches a human
Only three things escalate to human attention:
- Confidence below 0.75 — LLM isn't certain enough to act autonomously
- Verifier returns ESCALATE — the fix didn't work
- `REQUIRES_APPROVAL` actions — restart_pod requires human sign-off

Everything else is handled automatically.

---

## Phases built

### Application Layer (Phase 0–11)
- FastAPI REST API with full webhook CRUD (register, list, update, delete, enable, disable)
- Event ingestion with fan-out to all matching active webhooks
- Redis queue with per-user fairness scheduling — round-robin across user queues
- Global rate limiting with runtime configuration via API
- Mock receiver for local end-to-end testing

### Platform Layer (Phase 12–20)
- **Phase 12** — Multi-stage Docker builds — 1.82GB → 341MB, healthchecks on all services
- **Phase 13** — Environment-based config, zero hardcoded secrets
- **Phase 14** — Structured JSON logging with Logstash UDP shipping and error_type classification
- **Phase 15** — Prometheus metrics: events_received, delivery_success, delivery_failed, latency histograms, queue_depth
- **Phase 16** — Grafana + Prometheus stack with separate scrape jobs for API and worker
- **Phase 17** — Full Kubernetes migration: Deployments, Services, ConfigMaps, Secrets, RBAC
- **Phase 18** — HorizontalPodAutoscaler: workers scale 2→5 pods on CPU utilization
- **Phase 19** — GitHub Actions CI: lint → test → security scan → build
- **Phase 20** — CD pipeline: images pushed to GitHub Container Registry on merge

### Observability + Hardening (Phase 23–26)
- **Phase 23** — Distributed tracing: OpenTelemetry → Jaeger, full span propagation across API and worker
- **Phase 24** — Retry with exponential backoff (2s, 4s, 8s), dead letter queue, circuit breaker
- **Phase 25** — k6 load test: 23,402 requests, 155 req/s, p(95)=377ms, 0.00% failure rate
- **Phase 26** — Janitor: watches pod events, fetches crash logs, sends to Llama 3, returns diagnosis

### Intelligence + Security (Phase 27–29)
- **Phase 27** — Adaptive rate limiting: endpoint health score = success_rate × latency_factor, TCP-style congestion control
- **Phase 28** — Trivy container scanning in CI (blocks on critical CVEs), payload sanitization (sensitive keys + XSS)
- **Phase 29** — Async ML inference gateway: inference.requested events route to BentoML, predictions delivered via webhook callback

### Production Operations (Phase 30–34)
- **Phase 30** — AlertManager: Slack alerts for WorkerDown, APIDown, HighDeliveryFailureRate, HighQueueDepth
- **Phase 31** — ELK Stack: JSON logs ship via UDP → Logstash → Elasticsearch (nexus-api-*, nexus-worker-*) → Kibana
- **Phase 32** — Helm chart: one-command install, upgrade, rollback with full revision history
- **Phase 33** — Terraform IaC: VPC, EKS, ECR, NAT gateways, IAM — deployed and verified on AWS ap-south-1
- **Phase 34** — ArgoCD GitOps: auto-syncs Helm chart to Kubernetes on every push to main

### AIOps Layer (Phase 35)
- **Phase 35** — Autonomous AIOps engine: Detect → Analyze → Plan → Policy → Execute → Verify → Memory loop running every 30 seconds in Kubernetes with Prometheus metrics, ELK logs, Llama 3 intelligence, Kubernetes Python client for in-cluster operations, and RBAC-controlled deployment scaling

---

## Load test results
```
tool:     k6
stages:   ramp 10 → 50 → 100 VUs over 2m30s

requests:       23,402
req/sec:        155
p(95) latency:  377ms    ✓ threshold <500ms
failure rate:   0.00%    ✓ threshold <1%
checks passed:  100%
```

---

## Test suite

13 tests covering all critical paths — runs without any services:
```
✓ test_health
✓ test_register_webhook
✓ test_list_webhooks
✓ test_delete_webhook_not_found
✓ test_disable_webhook
✓ test_enable_webhook
✓ test_event_queued_per_user          ← verifies per-user queue key
✓ test_event_not_queued_for_unsubscribed_type
✓ test_delivery_retries_on_failure    ← verifies 3-attempt retry
✓ test_dlq                            ← verifies dead letter queue
✓ test_sanitizer                      ← verifies payload sanitization
✓ test_get_rate_limit
✓ test_update_rate_limit
```

Run:
```bash
DATABASE_URL=sqlite:///:memory: REDIS_HOST=localhost pytest tests/ -v
```

---

## Running locally

**Prerequisites:** Docker, Docker Compose
```bash
git clone https://github.com/kavangowda69/nexus-webhook-platform
cd nexus-webhook-platform
cp .env.example .env
# Add your SLACK_WEBHOOK_URL to .env
docker compose up
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Metrics | http://localhost:8000/metrics |
| Grafana | http://localhost:3000 (admin/admin) |
| Prometheus | http://localhost:9091 |
| Jaeger | http://localhost:16686 |
| Kibana | http://localhost:5601 |
| AlertManager | http://localhost:9093 |
| Inference Server | http://localhost:3001 |

**Register a webhook:**
```bash
curl -X POST http://localhost:8000/webhooks \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "url": "http://webhook_receiver:8001/test", "event_types": ["order.created"]}'
```

**Fire an event:**
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "event_type": "order.created", "payload": {"item": "book"}}'
```

**Fire an inference event:**
```bash
curl -X POST http://localhost:8000/webhooks \
  -H "Content-Type: application/json" \
  -d '{"user_id": "ai", "url": "http://webhook_receiver:8001/test", "event_types": ["inference.requested"]}'

curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"user_id": "ai", "event_type": "inference.requested", "payload": {"input": "classify this", "model": "echo"}}'
```

---

## Running on Kubernetes with Helm
```bash
minikube start --driver=docker --memory=4096 --cpus=2
eval $(minikube docker-env)

docker build -f dockerfile -t nexus-webhook-api:latest .
docker build -f dockerfile -t nexus-webhook-worker:latest .
docker build -f Dockerfile.receiver -t nexus-webhook-receiver:latest .
docker build -f aiops/Dockerfile -t nexus-aiops:latest ./aiops

helm install nexus helm/nexus
kubectl apply -f k8s/prometheus.yml
kubectl apply -f k8s/aiops.yml
kubectl apply -f helm/nexus/templates/aiops-rbac.yaml

kubectl get pods
kubectl logs deployment/aiops-engine -f
```

**Scale workers:**
```bash
helm upgrade nexus helm/nexus --set worker.replicas=3
```

**Watch AIOps in action:**
```bash
kubectl run crash-test --image=busybox --restart=Always -- sh -c "exit 1"
kubectl logs deployment/aiops-engine -f
```

---

## GitOps with ArgoCD
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f argocd/nexus-app.yaml
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Every push to main → CI builds image → GHCR → ArgoCD detects change → auto-deploys to Kubernetes.

---

## AWS Deployment (Terraform)

Deployed and verified on AWS — EKS cluster running in ap-south-1, 2 worker nodes confirmed Ready, images pushed to ECR, then destroyed.
```bash
cd terraform
terraform init
terraform plan -var-file=env/dev/terraform.tfvars
terraform apply -var-file=env/dev/terraform.tfvars
```

| Resource | Details |
|---|---|
| VPC | 10.0.0.0/16, 2 public + 2 private subnets across 2 AZs |
| EKS | Kubernetes 1.29, nexus-dev-cluster |
| Node Group | 2x t3.medium, autoscales 1→3 |
| ECR | 3 repositories with scan-on-push enabled |
| IAM | Least-privilege roles for EKS and nodes |

---

## Alerting

| Alert | Condition | Severity |
|---|---|---|
| WorkerDown | Worker not scraping for 30s | Critical |
| APIDown | API not scraping for 30s | Critical |
| HighDeliveryFailureRate | >0.1 failures/s for 1min | Critical |
| HighQueueDepth | Queue depth >50 for 1min | Warning |

---

## Security
```
Lint → Test → Trivy Container Scan → Build → Push to GHCR
```

Trivy blocks on critical CVEs. Payload sanitization strips sensitive keys (password, token, api_key, secret) and XSS patterns from every event payload before it enters the queue.

---

## CI/CD

1. **Lint** — flake8 across all Python source files
2. **Test** — 13 pytest tests, no services required
3. **Security Scan** — Trivy on each Docker image
4. **Build** — all images built and verified
5. **Push** — images pushed to GitHub Container Registry
6. **ArgoCD Sync** — triggers Kubernetes deployment

Images: `ghcr.io/kavangowda69/nexus-webhook-*`

---

## Project structure
```
nexus-webhook-platform/
├── api/
│   ├── main.py              # FastAPI app, all routes
│   ├── worker/worker.py     # Delivery, retry, circuit breaker,
│   │                        # adaptive rate, inference routing
│   ├── models/              # SQLAlchemy models
│   ├── database/            # DB connection
│   ├── logger.py            # Structured JSON + Logstash UDP + error_type
│   ├── metrics.py           # Prometheus counters, histograms, AIOps metrics
│   ├── tracing.py           # OpenTelemetry setup
│   └── sanitizer.py         # Payload sanitization
├── aiops/
│   ├── main.py              # Orchestration loop (30s interval)
│   ├── detector.py          # Prometheus + Kubernetes incident detection
│   ├── analyzer.py          # ELK logs + Ollama/Llama3 root cause analysis
│   ├── planner.py           # Cause → action mapping
│   ├── policy.py            # Safety gates: confidence, cooldown, limits
│   ├── executor.py          # Kubernetes API scaling and actions
│   ├── verifier.py          # Post-action metric verification
│   ├── memory.py            # Incident storage in Postgres
│   ├── kube_client.py       # Kubernetes Python client
│   ├── prometheus_client.py # Prometheus HTTP API client
│   ├── elk_client.py        # Elasticsearch log client
│   ├── runbooks/            # Remediation playbooks
│   └── Dockerfile
├── inference/
│   ├── model_server.py      # BentoML inference service
│   └── Dockerfile
├── janitor/
│   └── janitor.py           # Lightweight pod crash diagnostics
├── helm/nexus/              # Helm chart with AIOps deployment + RBAC
├── argocd/                  # ArgoCD application manifest
├── terraform/               # AWS VPC, EKS, ECR, IAM modules
├── k8s/                     # Raw Kubernetes manifests
├── logstash/pipeline/       # Logstash pipeline config
├── tests/
│   ├── test_api.py          # Original API tests
│   ├── test_nexus.py        # Comprehensive 13-test suite
│   └── load_test.js         # k6 load test
├── .github/workflows/       # CI + CD pipelines
├── grafana/                 # Grafana datasource provisioning
├── prometheus.yml           # Prometheus scrape config
├── prometheus_rules.yml     # Alert rules
├── alertmanager.yml         # AlertManager + Slack
├── dockerfile               # Multi-stage API/worker image
├── Dockerfile.receiver      # Multi-stage receiver image
└── docker-compose.yml       # Full local dev stack
```

---

## What this demonstrates

- Distributed event processing with queue-based fairness scheduling
- Production containerization and image optimization
- Kubernetes orchestration with Helm, HPA, and RBAC
- **Autonomous AIOps** — full incident lifecycle from detection to resolution without human intervention
- GitOps continuous delivery with ArgoCD
- AWS cloud deployment — EKS, ECR, VPC, IAM via Terraform
- Full observability: Prometheus metrics, structured logs, distributed traces
- Centralized log aggregation with ELK stack
- Real-time alerting with AlertManager and Slack
- DevSecOps pipeline with Trivy container scanning
- Adaptive systems design — rate limiting that responds to real endpoint behavior
- MLOps hook — async inference routing turning a webhook platform into AI infrastructure
- Comprehensive test suite covering all critical delivery paths
