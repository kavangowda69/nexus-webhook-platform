from prometheus_client import Counter, Histogram, Gauge

# Events
EVENTS_RECEIVED = Counter(
    "webhook_events_received_total",
    "Total number of events received",
    ["user_id", "event_type"]
)

# Deliveries
DELIVERIES_SUCCESS = Counter(
    "webhook_delivery_success_total",
    "Total successful webhook deliveries",
    ["webhook_id"]
)

DELIVERIES_FAILED = Counter(
    "webhook_delivery_failed_total",
    "Total failed webhook deliveries",
    ["webhook_id"]
)

# Latency
DELIVERY_LATENCY = Histogram(
    "webhook_delivery_latency_seconds",
    "Time taken to deliver a webhook",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# Queue depth
QUEUE_DEPTH = Gauge(
    "webhook_queue_depth",
    "Current number of jobs in redis queues"
)