# Nexus — Webhook Delivery Platform

A production-grade distributed webhook delivery system built phase by phase — from a basic FastAPI app to a full platform with Kubernetes, observability, security scanning, adaptive rate limiting, and async AI inference routing.

This isn't a project. It's a working system that handles real load (23k requests, 0% failure rate under test) with every layer you'd expect in a real engineering team's infrastructure.

---

## What it does

Clients register webhooks and publish events. Nexus queues the deliveries, routes them to the right endpoints, retries on failure, backs off when endpoints go down, and adapts its delivery rate based on endpoint health. Every request is traced end to end. Every failure is logged in structured JSON. The whole thing runs on Kubernetes with autoscaling — and if a pod crashes, an AI diagnostics service tells you why.
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
| Orchestration | Kubernetes, HPA |
| Observability | Prometheus, Grafana, Jaeger (OpenTelemetry) |
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
                       ┌───────────────┼───────────────┐
                       │               │               │
                  Prometheus        Grafana          Jaeger
                  (metrics)        (dashboards)     (traces)


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
- **Phase 12** — Multi-stage Docker builds — cut image size from 1.82GB to 341MB, added healthchecks across all services
- **Phase 13** — Environment-based config, no hardcoded secrets anywhere in the codebase
- **Phase 14** — Structured JSON logging across API and worker with timestamps, service names, and event context
- **Phase 15** — Prometheus metrics: `events_received`, `delivery_success`, `delivery_failed`, `delivery_latency`, `queue_depth`
- **Phase 16** — Grafana + Prometheus stack running in Docker Compose, both services scraping API and worker separately
- **Phase 17** — Full Kubernetes migration with Deployments, Services, ConfigMaps, Secrets for all 5 services
- **Phase 18** — HorizontalPodAutoscaler on workers — scales 2→5 pods based on CPU utilization
- **Phase 19** — GitHub Actions CI pipeline: lint → test → build on every push
- **Phase 20** — CD pipeline pushing images to GitHub Container Registry on merge to main

### Observability + Hardening (Phase 23–26)
- **Phase 23** — Distributed tracing with OpenTelemetry + Jaeger — full trace across API ingestion, queue push, and worker delivery
- **Phase 24** — Retry with exponential backoff (2s, 4s, 8s), dead letter queue for exhausted deliveries, circuit breaker that stops hammering unhealthy endpoints
- **Phase 25** — k6 load test: 23,402 requests, 155 req/s sustained, p(95)=377ms, 0.00% failure rate
- **Phase 26** — AI failure diagnostics: Janitor service watches Kubernetes pod events, fetches crash logs, sends to Llama 3 via Ollama, returns root cause + fix suggestion

### Intelligence + Security (Phase 27–29)
- **Phase 27** — Adaptive rate limiting: tracks per-endpoint success rate and latency, computes an endpoint health score, automatically increases or decreases delivery rate. TCP-style congestion control without ML
- **Phase 28** — DevSecOps: Trivy container scanning in CI pipeline (fails build on critical CVEs), payload sanitization layer strips dangerous keys and script injection before queuing
- **Phase 29** — Async AI inference gateway: events with `event_type: inference.requested` are routed to a BentoML model server, predictions are returned and delivered back via webhook callback. Your webhook platform becomes async ML infrastructure

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

## Running on Kubernetes

**Prerequisites:** minikube, kubectl
```bash
minikube start --driver=docker --memory=4096 --cpus=2
eval $(minikube docker-env)

docker build -f dockerfile -t nexus-webhook-api:latest .
docker build -f dockerfile -t nexus-webhook-worker:latest .
docker build -f Dockerfile.receiver -t nexus-webhook-receiver:latest .

kubectl apply -f k8s/
minikube service api-service --url
```

**Check autoscaling:**
```bash
kubectl get hpa
# NAME                 REFERENCE                   TARGETS      MINPODS   MAXPODS   REPLICAS
# webhook-worker-hpa   Deployment/webhook-worker   cpu: 8%/50%  2         5         2
```

---

## AI Failure Diagnostics

The janitor service runs outside the cluster, watches for pod failures, and uses a local LLM to explain what went wrong.

**Prerequisites:** Ollama installed (`brew install ollama`)
```bash
ollama serve
ollama pull llama3

cd janitor
python3 janitor.py
```

Example output:
```
============================================================
FAILURE DETECTED: webhook-worker-abc123
Reason: CrashLoopBackOff | Restarts: 5
============================================================

AI DIAGNOSIS:
Root cause: Memory pressure detected. Large payload processing
caused the worker to exceed its 256Mi memory limit.

Suggested fix: Increase memory limit from 256Mi to 512Mi in
k8s/worker.yml and redeploy.
============================================================
```

---

## Security

**Container scanning** runs on every CI push via Trivy. The pipeline fails if any critical, fixable CVEs are found in the built images.

**Payload sanitization** strips sensitive keys (`password`, `token`, `api_key`, `secret`, etc.) and script injection patterns from every incoming event payload before it reaches the queue.

CI pipeline order:
```
Lint → Test → Container Security Scan → Build → Push
```

---

## CI/CD

Every push to `main` triggers the full pipeline:

1. **Lint** — flake8 across all Python source files
2. **Test** — pytest with live Postgres and Redis service containers
3. **Security Scan** — Trivy scans each Docker image for critical CVEs
4. **Build** — all three images built and verified
5. **Push** — images pushed to GitHub Container Registry

Images: `ghcr.io/kavangowda69/nexus-webhook-*`

---

## Project structure
```
nexus-webhook-platform/
├── api/
│   ├── main.py              # FastAPI app, all routes
│   ├── worker/
│   │   └── worker.py        # Delivery worker, retry, circuit breaker,
│   │                        # adaptive rate limiting, inference routing
│   ├── models/              # SQLAlchemy models
│   ├── database/            # DB connection and session
│   ├── logger.py            # Structured JSON logging
│   ├── metrics.py           # Prometheus counters and histograms
│   ├── tracing.py           # OpenTelemetry setup
│   └── sanitizer.py         # Payload sanitization
├── inference/
│   ├── model_server.py      # BentoML inference service
│   └── Dockerfile
├── janitor/
│   └── janitor.py           # AI-powered pod failure diagnostics
├── k8s/                     # Kubernetes manifests
│   ├── api.yml
│   ├── worker.yml
│   ├── hpa.yml
│   ├── postgres.yml
│   ├── redis.yml
│   ├── receiver.yml
│   ├── configmap.yml
│   └── secret.yml
├── tests/
│   ├── test_api.py          # pytest unit tests
│   └── load_test.js         # k6 load test scenarios
├── .github/
│   └── workflows/
│       ├── ci.yml           # lint, test, security scan, build
│       └── cd.yml           # push to GHCR
├── grafana/                 # Grafana datasource provisioning
├── prometheus.yml           # Prometheus scrape config
├── dockerfile               # Multi-stage build for API and worker
├── Dockerfile.receiver      # Multi-stage build for receiver
└── docker-compose.yml       # Full local dev stack
```

---

## What this demonstrates

- Distributed event processing with queue-based job routing
- Production containerization and image optimization
- Kubernetes orchestration with horizontal autoscaling
- Full observability stack: metrics, logs, traces
- CI/CD pipeline with security scanning baked in
- Adaptive systems design — rate limiting that responds to real endpoint behavior
- AIOps — automated failure diagnosis using local LLMs
- MLOps hook — async inference routing turning a webhook platform into AI infrastructure
