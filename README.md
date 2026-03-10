# Multi-User Webhook Delivery System

A production-style webhook infrastructure built with **FastAPI, PostgreSQL, Redis, and Docker**.

The system allows users to register webhook endpoints, subscribe to platform events, and receive event payloads asynchronously through a **reliable, rate-limited, and fair delivery pipeline**.

This project demonstrates how modern backend systems implement **event-driven webhook delivery at scale**, similar to platforms like Stripe, Shopify, and GitHub.

---

# Assignment Coverage

This project implements all three required parts of the assignment:

### Part A — Core Delivery
- Webhook CRUD API
- Event ingestion endpoint
- Delivery worker
- Mock receiver service
- Fully containerized system using Docker Compose

### Part B — Rate Limiting
- Global delivery rate limit
- Runtime configuration endpoint
- Queued delivery when rate capacity is exceeded

### Part C — Multi-User Fairness
- Fair scheduling across users
- One user flooding events does not block others

---

# System Overview

The system supports three event types:

```
request.created
request.updated
request.deleted
```

Users can subscribe webhooks to any combination of these events.

The platform workflow:

1. Users register webhook endpoints
2. Applications publish events
3. The system fans out deliveries to subscribed webhooks
4. Delivery workers send HTTP POST requests to each endpoint

Event delivery is **asynchronous and queue-based** to ensure scalability and reliability.

---

# Architecture

```
                +----------------------+
                |      Client App      |
                |   (event producer)   |
                +----------+-----------+
                           |
                           | POST /events
                           v
                +----------------------+
                |      FastAPI API     |
                |   Event Ingestion    |
                +----------+-----------+
                           |
                           | Lookup webhooks
                           v
                +----------------------+
                |     PostgreSQL DB    |
                |  Webhook Metadata    |
                +----------+-----------+
                           |
                           | Create delivery jobs
                           v
                +----------------------+
                |       Redis Queue    |
                |  Delivery Job Queue  |
                +----------+-----------+
                           |
                           | Pop jobs
                           v
                +----------------------+
                |    Worker Service    |
                |  Webhook Dispatcher  |
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

## Webhook Registration

Users can register webhook endpoints and subscribe them to event types.

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

## Webhook CRUD API

| Method | Endpoint | Description |
|------|------|------|
| POST | /webhooks | Register webhook |
| GET | /webhooks | List webhooks |
| PUT | /webhooks/{id} | Update webhook |
| DELETE | /webhooks/{id} | Delete webhook |
| POST | /webhooks/{id}/enable | Enable webhook |
| POST | /webhooks/{id}/disable | Disable webhook |

Disabled webhooks do not receive deliveries.

---

## Event Ingestion

Applications publish events through:

```
POST /events
```

Example:

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

1. Finds active webhooks for the user
2. Filters by event type
3. Creates delivery jobs
4. Pushes them to Redis

---

# Queue-Based Delivery

Webhook deliveries are **not performed synchronously**.

Instead, the API pushes delivery jobs to **Redis**, which acts as a message queue.

Example job:

```
{
  "webhook_id": 1,
  "user_id": "123",
  "target_url": "http://receiver:9000/webhook",
  "event_type": "request.created",
  "payload": {...}
}
```

This architecture provides:

- Non-blocking API responses
- Reliable delivery processing
- Scalable worker-based architecture

---

# Delivery Worker

The worker service continuously processes delivery jobs.

Workflow:

1. Pop job from Redis queue
2. Respect global rate limit
3. Select next job based on fairness scheduler
4. Send HTTP POST request
5. Log success or failure

A delivery is considered successful when the webhook endpoint responds with **HTTP 2xx**.

Failed deliveries are logged (retry logic intentionally out of scope per assignment requirements).

---

# Rate Limiting (Part B)

The system implements a **global delivery rate limit**.

Example:

```
10 deliveries per second
```

If events arrive faster than the allowed rate:

- deliveries remain queued in Redis
- workers process them gradually as capacity becomes available

### Runtime Rate Limit Configuration

The system exposes an internal endpoint:

```
GET /rate-limit
POST /rate-limit
```

Example update:

```
{
  "limit_per_second": 20
}
```

This allows rate limits to be changed **without restarting the system**.

---

# Multi-User Fairness (Part C)

To prevent a single user from monopolizing the delivery pipeline, the system implements **fair scheduling across users**.

### Problem

If User A publishes thousands of events, they could block deliveries for other users.

### Solution

The worker uses **per-user queues with round-robin scheduling**.

Instead of processing a single global queue, deliveries are scheduled by user:

```
User A queue
User B queue
User C queue
```

The worker cycles between users:

```
A → B → C → A → B → C
```

This ensures:

- heavy users cannot block others
- smaller workloads are delivered quickly
- delivery latency remains consistent across users

---

# Running the System

The entire system starts with one command:

```
docker compose up --build
```

This launches:

- API service
- PostgreSQL
- Redis
- Worker service
- Mock webhook receiver

---


# Register a Webhook

```
curl -X POST http://localhost:8000/webhooks \
-H "Content-Type: application/json" \
-d '{
"user_id": "123",
"url": "http://host.docker.internal:9000/webhook",
"event_types": ["request.created"]
}'
```

---

# Publish an Event

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

# Observe Webhook Delivery

To observe webhook deliveries locally, you can run a simple receiver:

uvicorn receiver:app --port 9000

This prints received webhook payloads for testing purposes.

---

# Development Phases

The system was built incrementally:

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
Delivery worker

### Phase 7
Mock receiver

### Phase 8
Rate limiting implementation

### Phase 9
Multi-user fairness scheduling

### Phase 10
Docker Compose orchestration

