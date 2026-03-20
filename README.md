# Nexus — Webhook Delivery Platform

A production-grade distributed webhook delivery system built phase by phase — from a basic FastAPI app to a full platform with Kubernetes, observability, security scanning, adaptive rate limiting, async AI inference routing, alerting, centralized logging, Helm packaging, GitOps delivery via ArgoCD, and AWS deployment via Terraform.

This isn't a tutorial project. It's a working system that handles real load (23k requests, 0% failure rate under test), deployed and verified on AWS EKS, with full GitOps via ArgoCD.

---

## What it does

Clients register webhooks and publish events. Nexus queues the deliveries, routes them to the right endpoints, retries on failure, backs off when endpoints go down, and adapts its delivery rate based on endpoint health. Every request is traced end to end. Every failure is logged in structured JSON and searchable in Kibana. Alerts fire to Slack when things go wrong. The whole thing runs on Kubernetes with autoscaling — locally via Helm or on AWS EKS via Terraform — synced automatically via ArgoCD GitOps, and if a pod crashes, an AI diagnostics service tells you why.
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
| GitOps | ArgoCD |
| Cloud | AWS EKS, ECR, VPC, IAM |
| IaC | Terraform |
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
                        │     Kubernetes Cluster                │
                        │     (minikube local / AWS EKS)        │
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

  GitOps pipeline:
  git push → GitHub Actions (CI) → image pushed to GHCR
                                          │
                                      ArgoCD detects change
                                          │
                                      Auto-syncs Helm chart to Kubernetes

  Log pipeline:
  API/Worker → Logstash (UDP) → Elasticsearch → Kibana

  Inference path:
  Worker → BentoML Model Server → prediction → webhook callback

  Cloud infrastructure (Terraform):
  VPC → EKS Cluster → Node Group (t3.medium x2)
                   └→ ECR (3 repositories)
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
- **Phase 27** — Adaptive rate limiting: tracks per-endpoint health score (`success_rate * latency_factor`), automatically adjusts delivery rate — TCP-style congestion control
- **Phase 28** — Trivy container scanning in CI (fails build on critical CVEs), payload sanitization strips dangerous keys and XSS patterns before queuing
- **Phase 29** — Async AI inference gateway: `inference.requested` events route to BentoML model server, predictions delivered back via webhook callback

### Production Operations (Phase 30–34)
- **Phase 30** — AlertManager wired to Prometheus with Slack notifications — fires on `WorkerDown`, `APIDown`, `HighDeliveryFailureRate`, `HighQueueDepth`
- **Phase 31** — ELK Stack: structured JSON logs ship via UDP to Logstash, indexed in Elasticsearch by service (`nexus-api-*`, `nexus-worker-*`), searchable in Kibana
- **Phase 32** — Helm chart packaging all Kubernetes resources — one command install, upgrade, rollback with full revision history
- **Phase 33** — Terraform IaC provisioning AWS VPC, EKS cluster, ECR repositories, NAT gateways, and IAM roles — deployed and verified in `ap-south-1`, 2 EKS nodes confirmed `Ready`, images pushed to ECR, then destroyed
- **Phase 34** — ArgoCD GitOps: watches GitHub repo, automatically syncs Helm chart to Kubernetes on every push — full GitOps pipeline from commit to deployment

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

## GitOps with ArgoCD

ArgoCD watches this repository and automatically syncs the Helm chart to Kubernetes on every push. Any change to `helm/nexus/` triggers an automatic deployment.

**Install ArgoCD on your cluster:**
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

**Deploy the Nexus application:**
```bash
kubectl apply -f argocd/nexus-app.yaml
```

**Access the UI:**
```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Open https://localhost:8080
# Username: admin
# Password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

**GitOps flow:**
```
git push → CI builds + pushes image to GHCR
                │
            ArgoCD detects Helm chart change
                │
            Auto-syncs to Kubernetes cluster
                │
            Pods rolling updated automatically
```

For production clusters, set `ARGOCD_SERVER` and `ARGOCD_TOKEN` as GitHub secrets to enable automatic sync from the CD pipeline.

---

## AWS Deployment (Terraform)

Infrastructure provisioned via Terraform in `ap-south-1`. Deployed and verified — EKS cluster confirmed running, worker nodes showed `Ready`, images pushed to ECR — then destroyed.

**What gets provisioned:**

| Resource | Details |
|---|---|
| VPC | 10.0.0.0/16, 2 public + 2 private subnets across 2 AZs |
| EKS Cluster | Kubernetes 1.29, `nexus-dev-cluster` |
| Node Group | 2x t3.medium, autoscales 1→3 |
| ECR | 3 repositories — api, worker, receiver |
| NAT Gateways | 2x for private subnet outbound traffic |
| IAM | EKS cluster role + node role with least-privilege policies |
```bash
cd terraform
terraform init
terraform plan -var-file=env/dev/terraform.tfvars
terraform apply -var-file=env/dev/terraform.tfvars
```

**Push images to ECR after provisioning:**
```bash
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin <account_id>.dkr.ecr.ap-south-1.amazonaws.com

docker build -f dockerfile -t nexus-webhook-api:latest .
docker tag nexus-webhook-api:latest <ecr_api_url>:latest
docker push <ecr_api_url>:latest
```

**Connect kubectl to EKS and deploy via Helm:**
```bash
aws eks update-kubeconfig --region ap-south-1 --name nexus-dev-cluster
helm install nexus helm/nexus \
  --set api.image=<ecr_api_url> \
  --set worker.image=<ecr_worker_url> \
  --set receiver.image=<ecr_receiver_url>
```

**Tear down:**
```bash
terraform destroy -var-file=env/dev/terraform.tfvars
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

Trivy fails the build on any critical, fixable CVE. Payload sanitization strips sensitive keys and script injection from every event before it hits the queue.

---

## CI/CD

Every push to `main` triggers:

1. **Lint** — flake8 across all Python source files
2. **Test** — pytest with live Postgres and Redis service containers
3. **Security Scan** — Trivy scans each Docker image for critical CVEs
4. **Build** — all three images built and verified
5. **Push** — images pushed to GitHub Container Registry
6. **ArgoCD Sync** — triggers Kubernetes deployment via GitOps

Images: `ghcr.io/kavangowda69/nexus-webhook-*`

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
├── argocd/
│   └── nexus-app.yaml       # ArgoCD application manifest
├── terraform/               # AWS infrastructure as code
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── env/dev/
│   └── modules/
│       ├── vpc/
│       ├── eks/
│       ├── ecr/
│       └── iam/
├── k8s/                     # Raw Kubernetes manifests
├── logstash/pipeline/       # Logstash pipeline config
├── tests/
│   ├── test_api.py          # pytest unit tests
│   └── load_test.js         # k6 load test
├── .github/workflows/       # CI/CD pipelines
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
- GitOps continuous delivery with ArgoCD
- AWS cloud deployment — EKS, ECR, VPC, IAM via Terraform
- Full observability: metrics, structured logs, distributed traces
- Centralized log aggregation with ELK stack
- Real-time alerting with AlertManager and Slack
- CI/CD pipeline with security scanning baked in
- Adaptive systems design — rate limiting that responds to real endpoint behavior
- AIOps — automated failure diagnosis using local LLMs
- MLOps hook — async inference routing turning a webhook platform into AI infrastructure
