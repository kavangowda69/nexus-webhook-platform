# Webhook Delivery System

A production-style webhook infrastructure built with **FastAPI, PostgreSQL, Redis, and Docker**.  
This system allows users to register webhooks for specific events and reliably delivers event payloads asynchronously using a queue-based architecture.

The project demonstrates how modern backend systems handle **event-driven webhook delivery at scale**, similar to how platforms like **Stripe, Shopify, and GitHub** implement webhook infrastructure.

---

# System Overview

The system allows applications to:

1. Register webhook endpoints
2. Subscribe to specific event types
3. Emit events into the system
4. Deliver those events asynchronously to subscribed webhook endpoints

The architecture separates **API ingestion** from **event delivery** using Redis queues and worker services, ensuring reliability and scalability.

---

# Architecture

```
                +----------------------+
                |      Client App     |
                |  (event producer)   |
                +----------+----------+
                           |
                           | POST /events
                           v
                +----------------------+
                |      FastAPI API     |
                |  Event Ingestion     |
                +----------+-----------+
                           |
                           | Store webhook configs
                           v
                +----------------------+
                |     PostgreSQL DB    |
                |  Webhook Metadata    |
                +----------+-----------+
                           |
                           | Push delivery jobs
                           v
                +----------------------+
                |       Redis Queue    |
                |  webhook_deliveries  |
                +----------+-----------+
                           |
                           | Pop jobs
                           v
                +----------------------+
                |   Worker Service     |
                | Webhook Dispatcher   |
                +----------+-----------+
                           |
                           | HTTP POST
                           v
                +----------------------+
                |   Mock Receiver      |
                | Webhook Consumer     |
                +----------------------+
```

---

# Project Structure

```
webhook-delivery-system
│
├── api/
│   ├── database/
│   │   └── database.py
│   │
│   ├── worker/
│   │   └── worker.py
│   │
│   └── main.py
│
├── docker-compose.yml
├── dockerfile
├── requirements.txt
└── README.md
```

---

# Features

### Webhook Registration
Users can register webhook endpoints and subscribe them to specific event types.

Example:

```
POST /webhooks
```

Request body:

```
{
  "url": "http://receiver:9000/webhook",
  "event_types": ["request.created", "request.updated"]
}
```

---

### Webhook CRUD API

Supported operations:

| Method | Endpoint | Description |
|------|------|------|
| POST | /webhooks | Register webhook |
| GET | /webhooks | List webhooks |
| PUT | /webhooks/{id} | Update webhook |
| DELETE | /webhooks/{id} | Delete webhook |
| POST | /webhooks/{id}/enable | Enable webhook |
| POST | /webhooks/{id}/disable | Disable webhook |

---

### Event Ingestion

Applications emit events into the system.

```
POST /events
```

Example request:

```
{
  "user_id": "123",
  "event_type": "request.created",
  "payload": {
    "request_id": 42
  }
}
```

The system:

1. Finds matching active webhooks
2. Creates delivery jobs
3. Pushes jobs to Redis queue

---

### Queue-Based Delivery

Instead of sending webhooks synchronously, the API pushes jobs into **Redis**.

Example job structure:

```
{
  "webhook_id": 1,
  "target_url": "http://receiver:9000/webhook",
  "event_type": "request.created",
  "payload": {...}
}
```

This architecture ensures:

- Non-blocking API responses
- Scalable event processing
- Worker-based delivery

---

### Worker Service

The worker continuously polls the Redis queue:

```
while True:
    job = queue.pop()
    send_webhook(job)
```

The worker:

1. Pops delivery job from queue
2. Sends HTTP POST request to webhook endpoint
3. Logs success or failure

---

### Mock Webhook Receiver

A small receiver service simulates external webhook consumers.

When it receives a webhook:

```
POST /webhook
```

It prints:

```
Webhook received:
{
  "event_type": "request.created",
  "payload": {...}
}
```

---

# Tech Stack

| Technology | Purpose |
|------|------|
| FastAPI | API service |
| PostgreSQL | Persistent webhook storage |
| Redis | Message queue for delivery jobs |
| Docker | Containerization |
| Docker Compose | Multi-service orchestration |
| Python | Backend implementation |

---

# Why This Architecture

Webhook systems must handle:

- asynchronous delivery
- large volumes of events
- unreliable external endpoints

Using a **queue-based architecture** provides:

### Reliability

Events are stored in Redis before delivery.

### Scalability

Workers can scale horizontally.

### Isolation

API service remains responsive while delivery happens asynchronously.

---

# Running the System

The entire system runs with a single command using Docker Compose.

### Start the system

```
docker compose up --build
```

This starts:

- API service
- PostgreSQL
- Redis
- Worker service
- Mock receiver

---

### Verify API health

```
curl localhost:8000/health
```

Expected response:

```
{"status":"ok"}
```

---

### Register a webhook

```
curl -X POST http://localhost:8000/webhooks \
-H "Content-Type: application/json" \
-d '{
"url": "http://host.docker.internal:9000/webhook",
"event_types": ["request.created"]
}'
```

---

### Emit an event

```
curl -X POST http://localhost:8000/events \
-H "Content-Type: application/json" \
-d '{
"user_id": "123",
"event_type": "request.created",
"payload": {
"request_id": 42
}
}'
```

---

### Observe webhook delivery

The receiver container logs:

```
Webhook received:
{
  "event_type": "request.created",
  "payload": {
    "request_id": 42
  }
}
```

---

# Development Phases

The project was implemented incrementally through structured commits.

### Phase 1
FastAPI service setup

### Phase 2
Webhook database model

### Phase 3
Webhook CRUD API

### Phase 4
Event ingestion endpoint

### Phase 5
Redis queue integration

### Phase 6
Webhook delivery worker

### Phase 7
Mock webhook receiver

### Phase 8
Docker Compose orchestration

---

