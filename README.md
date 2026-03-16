# Nexus — Webhook Delivery Platform

A production-grade distributed webhook delivery system built phase by phase — from a basic FastAPI app to a full platform with Kubernetes, observability, security scanning, adaptive rate limiting, async AI inference routing, alerting, centralized logging, and Helm packaging.

This isn't a tutorial project. It's a working system that handles real load (23k requests, 0% failure rate under test) with every layer you'd expect in a real engineering team's infrastructure.

---

## What it does

Clients register webhooks and publish events. Nexus queues the deliveries, routes them to the right endpoints, retries on failure, backs off when endpoints go down, and adapts its delivery rate based on endpoint health. Every request is traced end to end. Every failure is logged in structured JSON and searchable in Kibana. Alerts fire to Slack when things go wrong. The whole thing runs on Kubernetes with autoscaling — and if a pod crashes, an AI diagnostics service tells you why.
```
Client → POST /events
           │
           ▼
       FastAPI API  ──→  Payload Sanitization
           │
       Redis Queue (per user, round-robin fairness)
           │
       Worker Cluster (2–5 pods, autoscaled)
           │         │
           │         └──→ inference.requested → BentoML Model Server
           │
       Webhook Endpoint
```

---

## Tech stack

| Layer | Tools |
|---|---|
| API | FastAPI, SQLAlchemy, Postgres |
| Queue | Redis |
| Containers | Docker (multi-stage, 341MB images) |
| Orchestration | Kubernetes, Helm, HPA |
| Observability | Prometheus, Grafana, Jaeger (OpenTelemetry) |
| Log Aggregation | Elasticsearch, Logstash, Kibana (ELK) |
| Alerting | AlertManager, Slack |
| CI/CD | GitHub Actions, GitHub Container Registry |
| Security | Trivy container scanning, payload sanitization |
| AIOps | Ollama, Llama 3 |
| ML Inference | BentoML |
| Load testing | k6 |

---

## Architecture
```
                        ┌──────────────────────────────────────┐
                        │          Kubernetes Cluster           │
                        │                                      │
  Client                │  ┌──────────┐    ┌───────────────┐  │
    │                   │  │   API    │    │    Worker     │  │
    │ POST /events       │  │  (pods)  │    │  (2–5 pods)   │  │
    └──────────────────▶│  └────┬─────┘    └──────┬────────┘  │
                        │       │                  │           │
                        │       ▼                  ▼           │
                        │  ┌─────────┐    ┌──────────────┐    │
                        │  │  Redis  │───▶│   Postgres   │    │
                        │  └─────────┘    └──────────────┘    │
                        │                                      │
                        └──────────────────────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
         Prometheus               Grafana                    Jaeger
         (metrics)               (dashboards)               (traces)
              │
         AlertManager
         (Slack alerts)

  Log pipeline:
  API/Worker → Logstash (UDP) → Elasticsearch → Kibana

  Inference path:
  Worker → BentoML Model Server → prediction → webhook callback
```

---

## Phases built

### Application Layer (Phase 0–11)
- FastAPI REST API with full webhook CRUD
- Event ingestion and delivery pipeline
- Redis queue with per-user fairness scheduling (round-robin)
- Global rate limiting with dynamic control via API
- Mock receiver for local end-to-end testing
- Postgres persistence for webhooks and deliveries

### Platform Layer (Phase 12–20)
- **Phase 12** — Multi-stage Docker builds — cut image size from 1.82GB to 341MB, healthchecks across all services
- **Phase 13** — Environment-based config, no hardcoded secrets anywhere in the codebase
- **Phase 14** — Structured JSON logging across API and worker with timestamps, service names, and event context
- **Phase 15** — Prometheus metrics: `events_received`, `delivery_success`, `delivery_failed`, `delivery_latency`, `queue_depth`
- **Phase 16** — Grafana + Prometheus stack, both scraping API and worker separately
- **Phase 17** — Full Kubernetes migration with Deployments, Services, ConfigMaps, Secrets
- **Phase 18** — HorizontalPodAutoscaler on workers — scales 2→5 pods based on CPU utilization
- **Phase 19** — GitHub Actions CI pipeline: lint → test → security scan → build on every push
- **Phase 20** — CD pipeline pushing images to GitHub Container Registry on merge to main

### Observability + Hardening (Phase 23–26)
- **Phase 23** — Distributed tracing with OpenTelemetry + Jaeger — full trace across API ingestion and worker delivery
- **Phase 24** — Retry with exponential backoff (2s, 4s, 8s), dead letter queue, circuit breaker
- **Phase 25** — k6 load test: 23,402 requests, 155 req/s, p(95)=377ms, 0.00% failure rate
- **Phase 26** — AI failure diagnostics: Janitor watches pod events, fetches crash logs, sends to Llama 3, returns root cause + fix

### Intelligence + Security (Phase 27–29)
- **Phase 27** — Adaptive rate limiting: tracks per-endpoint health score (`success_rate * latency_factor`), automatically adjusts delivery rate. TCP-style congestion control
- **Phase 28** — Trivy container scanning in CI (fails build on critical CVEs), payload sanitization strips dangerous keys and XSS patterns before queuing
- **Phase 29** — Async AI inference gateway: `inference.requested` events route to BentoML model server, predictions delivered back via webhook callback

### Production Operations (Phase 30–32)
- **Phase 30** — AlertManager wired to Prometheus with Slack notifications — fires on `WorkerDown`, `APIDown`, `HighDeliveryFailureRate`, `HighQueueDepth`
- **Phase 31** — ELK Stack: structured JSON logs ship via UDP to Logstash, indexed in Elasticsearch by service (`nexus-api-*`, `nexus-worker-*`), searchable in Kibana
- **Phase 32** — Helm chart packaging all Kubernetes resources — one command install, upgrade, rollback with full revision history

---

## Load test results
```
tool:            k6
stages:          ramp 10 → 50 → 100 VUs over 2m30s

requests:        23,402
req/sec:         155
p(95) latency:   377ms    ✓ threshold <500ms
failure rate:    0.00%    ✓ threshold <1%
checks passed:   100%
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
  -d '{"user_id": "ai_user", "url": "http://webhook_receiver:8001/test", "event_types": ["inference.requested"]}'

curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"user_id": "ai_user", "event_type": "inference.requested", "payload": {"input": "classify this", "model": "echo"}}'
```

---

## Running on Kubernetes with Helm

**Prerequisites:** minikube, kubectl, helm
```bash
minikube start --driver=docker --memory=4096 --cpus=2
eval $(minikube docker-env)

docker build -f dockerfile -t nexus-webhook-api:latest .
docker build -f dockerfile -t nexus-webhook-worker:latest .
docker build -f Dockerfile.receiver -t nexus-webhook-receiver:latest .

# Install
helm install nexus helm/nexus

# Check status
helm list
kubectl get pods

# Scale workers
helm upgrade nexus helm/nexus --set worker.replicas=3

# Rollback
helm rollback nexus 1
```

---

## Alerting

AlertManager fires Slack alerts for:

| Alert | Condition | Severity |
|---|---|---|
| WorkerDown | Worker not scraping for 30s | Critical |
| APIDown | API not scraping for 30s | Critical |
| HighDeliveryFailureRate | >0.1 failures/s for 1min | Critical |
| HighQueueDepth | Queue depth >50 for 1min | Warning |

---

## AI Failure Diagnostics
```bash
ollama serve
ollama pull llama3

cd janitor
python3 janitor.py
```

Example output:
```
FAILURE DETECTED: webhook-worker-abc123
Reason: CrashLoopBackOff | Restarts: 5

AI DIAGNOSIS:
Root cause: Memory pressure detected. Large payload processing
caused the worker to exceed its 256Mi memory limit.

Suggested fix: Increase memory limit from 256Mi to 512Mi in
helm/nexus/values.yaml and run helm upgrade nexus helm/nexus.
```

---

## Security

CI pipeline order:
```
Lint → Test → Container Security Scan (Trivy) → Build → Push
```

Trivy fails the build on any critical, fixable CVE found in Docker images. Payload sanitization strips sensitive keys and script injection from every event before it hits the queue.

---

## Project structure
```
nexus-webhook-platform/
├── api/
│   ├── main.py              # FastAPI app, all routes
│   ├── worker/
│   │   └── worker.py        # Delivery, retry, circuit breaker,
│   │                        # adaptive rate limiting, inference routing
│   ├── models/              # SQLAlchemy models
│   ├── database/            # DB connection
│   ├── logger.py            # Structured JSON + Logstash UDP shipping
│   ├── metrics.py           # Prometheus counters and histograms
│   ├── tracing.py           # OpenTelemetry setup
│   └── sanitizer.py         # Payload sanitization
├── inference/
│   ├── model_server.py      # BentoML inference service
│   └── Dockerfile
├── janitor/
│   └── janitor.py           # AI-powered pod failure diagnostics
├── helm/
│   └── nexus/               # Helm chart
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
├── k8s/                     # Raw Kubernetes manifests
├── logstash/
│   └── pipeline/
│       └── nexus.conf       # Logstash pipeline config
├── tests/
│   ├── test_api.py          # pytest unit tests
│   └── load_test.js         # k6 load test
├── .github/
│   └── workflows/
│       ├── ci.yml           # lint, test, trivy, build
│       └── cd.yml           # push to GHCR
├── grafana/                 # Grafana datasource provisioning
├── prometheus.yml           # Prometheus scrape config
├── prometheus_rules.yml     # Alert rules
├── alertmanager.yml         # AlertManager + Slack config
├── dockerfile               # Multi-stage API/worker image
├── Dockerfile.receiver      # Multi-stage receiver image
└── docker-compose.yml       # Full local dev stack
```

---

## What this demonstrates

- Distributed event processing with queue-based job routing
- Production containerization and image optimization
- Kubernetes orchestration with Helm and horizontal autoscaling
- Full observability: metrics, structured logs, distributed traces
- Centralized log aggregation with ELK stack
- Real-time alerting with AlertManager and Slack
- CI/CD pipeline with security scanning baked in
- Adaptive systems design — rate limiting that responds to real endpoint behavior
- AIOps — automated failure diagnosis using local LLMs
- MLOps hook — async inference routing turning a webhook platform into AI infrastructure
