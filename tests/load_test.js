import http from 'k6/http';
import { check, sleep } from 'k6';

// ----------------------------
// Test Configuration
// ----------------------------
export const options = {
  stages: [
    { duration: '30s', target: 10 },   // ramp up to 10 users
    { duration: '60s', target: 50 },   // ramp up to 50 users
    { duration: '30s', target: 100 },  // spike to 100 users
    { duration: '30s', target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% of requests under 500ms
    http_req_failed: ['rate<0.01'],    // less than 1% failure rate
  },
};

const BASE_URL = 'http://localhost:8000';

// ----------------------------
// Setup — runs once before test
// ----------------------------
export function setup() {
  const payload = JSON.stringify({
    user_id: 'loadtest_user',
    url: 'http://localhost:8001/test',
    event_types: ['order.created', 'order.updated'],
  });

  const res = http.post(`${BASE_URL}/webhooks`, payload, {
    headers: { 'Content-Type': 'application/json' },
  });

  check(res, { 'webhook registered': (r) => r.status === 200 });

  return { webhook_id: res.json('id') };
}

// ----------------------------
// Main — runs for each virtual user
// ----------------------------
export default function () {
  const payload = JSON.stringify({
    user_id: 'loadtest_user',
    event_type: 'order.created',
    payload: { item: 'book', quantity: 1 },
  });

  const res = http.post(`${BASE_URL}/events`, payload, {
    headers: { 'Content-Type': 'application/json' },
  });

  check(res, {
    'status is 200': (r) => r.status === 200,
    'deliveries created': (r) => r.json('deliveries_created') > 0,
  });

  sleep(0.1);
}