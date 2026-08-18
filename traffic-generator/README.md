# Traffic Generator

This directory contains the Locust-based traffic generator for load testing the Order Management System.

## Overview

The traffic generator simulates realistic user behavior across all services in the platform:

- **Order Service** — Create and list orders
- **Payment Service** — List payments and process new payments
- **Notification Service** — Send notification requests

## Architecture

```
Locust Master (8089)
  │
  ├── OrderUser (30% of traffic)
  │     ├── POST /orders (create order)
  │     ├── GET /orders (list orders)
  │     ├── GET /metrics
  │     └── GET /health
  │
  ├── PaymentUser (25% of traffic)
  │     ├── GET /payments (list payments)
  │     ├── POST /payments (process payment)
  │     └── GET /health
  │
  └── NotificationUser (20% of traffic)
        ├── POST /notifications (send notification)
        └── GET /health
```

## Quick Start

### Run Locust Standalone

```bash
cd traffic-generator
locust -f locustfile.py --host http://nginx --web-port 8089
```

Then open http://localhost:8089 in your browser.

### Run with Docker Compose

```bash
cd traffic-generator
docker compose up -d
```

Then open http://localhost:8089 in your browser.

### Run Headless (CI/CD)

```bash
cd traffic-generator
locust -f locustfile.py \
  --host http://nginx \
  --users 500 \
  --spawn-rate 50 \
  --run-time 10m \
  --headless \
  --csv results/locust_results \
  --html results/report.html
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCUST_HOST` | `http://nginx` | Target API base URL |
| `LOCUST_USERS` | `100` | Number of concurrent users |
| `LOCUST_SPAWN_RATE` | `10` | Users spawned per second |
| `LOCUST_RUN_TIME` | `5m` | Duration of the test |
| `LOCUST_MODE` | `standalone` | Locust mode (standalone or master) |

## Test Scenarios

### OrderUser (30% of traffic)
- Creates orders with random customer/product data
- Lists all orders
- Checks metrics endpoint
- Health check

### PaymentUser (25% of traffic)
- Lists payments
- Processes payments with random order/amount data
- Health check

### NotificationUser (20% of traffic)
- Sends notifications of various types
- Health check

## Observing Results

During and after load tests, monitor the platform using:

- **Prometheus** — `http://localhost:9090` (metrics)
- **Grafana** — `http://localhost:3000` (dashboards)
- **Locust Web UI** — `http://localhost:8089` (test results)

Key metrics to observe:

- API response times (p50, p95, p99)
- Requests per second
- Error rates
- CPU and memory usage per service
- Kubernetes HPA scaling events
- Redis cache hit ratio
- PostgreSQL connection pool usage
- Kafka consumer lag
- RabbitMQ queue depth
- Distributed traces (Jaeger/Tempo)

## Results

Test results are saved to the `results/` directory:

- `results/locust_results_stats.csv` — Aggregate statistics
- `results/locust_results_stats_history.csv` — Per-second statistics
- `results/locust_results_failures.csv` — Failure details
- `results/locust_results_exceptions.csv` — Exception details
- `results/report.html` — HTML report (headless mode)
- `results/locust.log` — Log output