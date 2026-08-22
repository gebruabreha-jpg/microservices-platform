Microservices Platform Review Plan:-
100 Steps to Production-Ready Platform
Phase 1: Infrastructure Foundation (Steps 1-20)
Docker Compose Validation
Run docker compose config in platform/ — verify no YAML errors
Run docker compose up -d — all services start without errors
Check docker compose ps — all containers show "healthy" or "running"
Verify no container restarts in loop (docker compose logs --tail=50)
Check all required ports are available: 5432, 6379, 5672, 9092, 80, 3000, 3100, 3200, 4317, 9090
PostgreSQL
docker exec -it postgres psql -U admin -d appdb — connect successfully
Verify tables exist: \dt — should show orders, payments, notifications
Check Postgres init scripts ran: SELECT * FROM orders LIMIT 1; — no errors
Verify connection pooling works: SHOW max_connections;
Test pgadmin: http://localhost:5050 — login with admin@localdomain.com/admin
Redis
docker exec -it redis redis-cli ping — returns PONG
docker exec -it redis redis-cli ping -a secret — auth works with password
Check Redis config applied: docker exec -it redis redis-cli CONFIG GET maxmemory — returns 256mb
Verify AOF persistence: docker exec -it redis redis-cli CONFIG GET appendonly — returns yes
Test Redis Insight: http://localhost:5540 — connect to redis:6379
Kafka
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list — shows orders, notifications
Produce test message: kafka-console-producer --topic orders --bootstrap-server localhost:9092
Consume test message: kafka-console-consumer --topic orders --from-beginning --bootstrap-server localhost:9092
Check Kafka UI: http://localhost:8080 — shows topics and messages
Verify AUTO_CREATE_TOPICS_ENABLE=true is set
RabbitMQ
curl http://localhost:15672/api/queues -u admin:secret — returns JSON with queues
Verify DLQ exists: check for dlq queue in management UI
Verify notifications queue has x-dead-letter-exchange: dlx argument
Test publish/consume: use management UI to send test message
Check RabbitMQ definitions loaded: rabbitmqctl list_queues
Phase 2: NGINX Gateway (Steps 26-35)
curl http://localhost/health/order — returns 200 with order-service health
curl http://localhost/health/payment — returns 200 with payment-service health
curl http://localhost/health/notification — returns 200 with notification-service health
curl http://localhost/metrics/order — returns Prometheus metrics text
curl http://localhost/metrics/payment — returns Prometheus metrics text
curl http://localhost/metrics/notification — returns Prometheus metrics text
curl -X POST http://localhost/orders -H "Content-Type: application/json" -d "{}" — routes to order-service
curl -X POST http://localhost/payments -H "Content-Type: application/json" -d "{}" — routes to payment-service
curl -X POST http://localhost/notifications -H "Content-Type: application/json" -d "{}" — routes to notification-service
Test CORS headers: curl -I -X OPTIONS http://localhost/orders — returns CORS headers
Phase 3: Observability Stack (Steps 36-55)
Prometheus
http://localhost:9090/targets — all targets show "UP"
Verify scrape jobs: order-service, payment-service, notification-service, redis-exporter, node-exporter, cadvisor
Check redis-exporter metrics: query redis_connected_clients — returns value
Check node-exporter metrics: query node_cpu_seconds_total — returns value
Check cadvisor metrics: query container_cpu_usage_seconds_total — returns value
Grafana
http://localhost:3000 — login with admin/admin
Verify datasources configured: Configuration → Data Sources — shows Prometheus, Loki, Tempo
Verify dashboards loaded: Dashboards → Browse — shows placeholder dashboard
Test Prometheus query: Explore → select Prometheus → query up — returns metrics
Test Loki query: Explore → select Loki → query {service="order-service"} — returns logs (after generating traffic)
Loki + Promtail
Generate test traffic: curl http://localhost/orders (run 5 times)
Query Loki: curl "http://localhost:3100/loki/api/v1/query_range?query={service=\"order-service\"}&limit=10"
Verify logs contain JSON structure with timestamp, level, service, message
Check Promtail is running: docker logs promtail — no errors
Verify Promtail config mounted: docker inspect promtail | grep -A 10 Mounts
Tempo
Generate traced request: curl -H "X-Correlation-ID: test-123" http://localhost/orders
Query Tempo: curl "http://localhost:3200/api/traces?service=order-service&operation=POST%20%2Forders"
Verify trace contains spans: db.insert_order, kafka.publish_order_created, redis.cache_order
Check trace duration > 0ms
Verify trace has trace_id matching log correlation
OTel Collector
Check OTel Collector logs: docker logs otel-collector — no errors
Verify receiving OTLP: check for "traces" and "metrics" in logs
Test OTLP endpoint: curl -H "Content-Type: application/x-protobuf" http://localhost:4317 — returns 200 or 404 (expected)
Verify metrics exported to Prometheus: query order_requests_total in Prometheus — should increase after requests
Verify traces exported to Tempo: repeat step 53 after generating more traffic
Phase 4: Order Service Code Review (Steps 61-75)
main.py
Verify SERVICE_NAME=order-service env var set
Verify setup_tracing() called before any routes
Verify get_meter() creates counter and histogram
Verify /metrics endpoint returns Prometheus text format
Verify rate limiting configured (if slowapi installed)
Verify shutdown event logs properly
routes/order_router.py
Verify /health endpoint calls health_check()
Verify /metrics endpoint uses generate_latest()
Verify /orders GET calls list_orders() with limit/offset
Verify /orders POST calls create_order() with correlation_id
service/order_service.py
Verify create_order has custom spans: create_order, db.insert_order, kafka.publish_order_created, redis.cache_order
Verify metrics recorded: otlp_request_count, otlp_request_duration, otlp_cache_hit/miss
Verify log_event called with correlation_id
Verify Kafka event published with correct topic orders
Verify cache invalidation: cache_delete("orders:list:*")
repository/order_repository.py
Verify create_order uses parameterized queries (no SQL injection)
Verify get_all_orders has LIMIT/OFFSET pagination
Verify connection released in finally or if own_conn
core/database.py
Verify PostgreSQL pool configured with POSTGRES_POOL_SIZE
Verify Redis client uses REDIS_PASSWORD
Verify Kafka producer has acks="all" and retries=3
Verify publish_kafka_event has retry decorator
Verify check_dependencies checks postgres and redis
tests/test_app.py
Run pytest services/order-service/tests/ — all tests pass
Verify test coverage for /orders POST endpoint
Verify test coverage for /health endpoint
Phase 5: Payment Service Code Review (Steps 86-100)
main.py
Verify SERVICE_NAME=payment-service env var set
Verify Kafka consumer thread started on startup
Verify /metrics endpoint returns Prometheus text format
routes/payment_router.py
Verify /payments GET calls list_payments()
Verify /payments POST calls process_payment() with correlation_id
Verify /health endpoint works
service/payment_service.py
Verify process_payment has custom spans: process_payment, db.insert_payment, rabbitmq.publish_notification
Verify idempotency check: get_payment_by_order_id before insert
Verify metrics recorded on success and error
Verify log_event called with correlation_id
Verify RabbitMQ message published to notifications queue
Verify Kafka consumer has span: consume_order_event
core/database.py
Verify RabbitMQ connection uses RABBITMQ_USER/RABBITMQ_PASS
Verify queue_rabbitmq_job has retry decorator
Phase 6: Notification Service Code Review (Steps 101-115)
main.py
Verify SERVICE_NAME=notification-service env var set
Verify both consumer threads started: start_consumer and start_dlq_consumer
routes/notification_router.py
Verify /notifications POST calls send_notification()
Verify /health endpoint works
service/notification_service.py
Verify send_notification has custom spans: send_notification, db.insert_notification
Verify handle_notification has span with messaging.system=rabbitmq
Verify DLQ counter incremented on basic_nack
Verify start_dlq_consumer has span for handle_dlq_message
Verify setup_dlq called before consuming
core/database.py
Verify setup_dlq declares dlx exchange and dlq queue
Verify queue_rabbitmq_job uses delivery_mode=2 (persistent)
Phase 7: Traffic Generator (Steps 116-125)
cd traffic-generator && docker compose up -d — starts successfully
http://localhost:8089 — Locust UI loads
Start test with 10 users, spawn rate 1 — no errors in UI
Verify requests appear in Locust statistics
Check /results/ directory — CSV files created after test stop
Verify locust_summary.csv has duration, total_requests, success_rate
Verify locust_requests.csv has per-request details
Verify locust_failures.csv has failure records
Test all 3 user classes: OrderUser, PaymentUser, NotificationUser
Verify MixedUser routes to correct endpoints
Phase 8: End-to-End Flow Testing (Steps 126-140)
curl -X POST http://localhost/orders -H "Content-Type: application/json" -d '{"customer_id":1,"product_id":1,"quantity":1,"amount":10.0}'
Verify response: {"id": 1, "status": "created", "correlation_id": "..."}
Check PostgreSQL: SELECT * FROM orders; — new row exists
Check Redis: redis-cli GET order:1 — returns JSON
Check Kafka: kafka-console-consumer --topic orders --from-beginning --bootstrap-server localhost:9092 — message appears
Wait 5 seconds for consumer
Check PostgreSQL: SELECT * FROM payments; — payment row exists (from Kafka consumer)
Check RabbitMQ: rabbitmqctl list_queues name messages — notifications queue has message
Wait 2 seconds for consumer
Check PostgreSQL: SELECT * FROM notifications; — notification row exists
Verify trace in Tempo: trace_id from step 127 correlation_id
Verify metrics in Prometheus: order_requests_total increased
Verify logs in Loki: {service="order-service"} shows "Order created"
Test error flow: send invalid request, verify DLQ message appears
Verify circuit breaker triggers after repeated failures
Phase 9: Security Manifests Review (Steps 141-150)
Verify security/cert-manager/cluster-issuer.yaml has valid Let's Encrypt config
Verify security/cert-manager/certificate.yaml has correct DNS names
Verify security/external-secrets/cluster-secret-store.yaml has Vault endpoint
Verify security/external-secrets/external-secret-order.yaml references correct secrets
Verify security/service-mesh/istio/peer-authentication.yaml has STRICT mTLS
Verify security/service-mesh/istio/destination-rules.yaml has all 3 services
Verify security/service-mesh/istio/gateway.yaml references correct TLS secret
Verify all security YAMLs are valid: kubectl apply --dry-run=client -f security/...
Verify no hardcoded secrets in manifests
Verify RBAC rules exist for external-secrets service account
Phase 10: Documentation & Developer Experience (Steps 151-165)
Verify README.md has correct architecture diagram
Verify README.md has working quick start commands
Verify all service ports listed in README are correct
Verify .env.example exists with all required variables (create if missing)
Verify Makefile exists with up, down, test, logs targets (create if missing)
Verify PowerShell scripts exist for Windows users (create if missing)
Verify each service has README.md with setup instructions
Verify traffic-generator/README.md explains how to run Locust
Verify platform/scripts/ has executable up.sh, down.sh, restart.sh, reset.sh
Verify security/README.md has deployment order and prerequisites
Phase 11: Code Quality (Steps 161-175)
Run flake8 services/ — no critical errors
Run pylint services/ — score > 7/10
Verify no hardcoded passwords in code (search for "secret", "password", "admin")
Verify all try/except blocks log exceptions properly
Verify all database connections use parameterized queries
Verify no SQL injection vulnerabilities
Verify all external inputs validated with Pydantic schemas
Verify all secrets loaded from environment variables
Verify no debug mode enabled in production code
Verify all file operations use context managers (with)
Phase 12: Performance & Resilience (Steps 171-185)
Load test: 100 concurrent users for 5 minutes — no errors
Verify Redis cache hit ratio > 80% under load
Verify PostgreSQL connection pool doesn't exhaust
Verify Kafka consumer lag stays near 0
Verify RabbitMQ queue depth doesn't grow unbounded
Test circuit breaker: stop Kafka, verify order-service degrades gracefully
Test retry logic: stop RabbitMQ temporarily, verify payment-service retries
Test idempotency: send same payment twice, verify no duplicate
Verify rate limiting works: send 200 requests in 1 second — some return 429
Verify health checks return 200 under load
Phase 13: Production Readiness (Steps 186-200)
Verify all containers have restart: always policy
Verify all services have resource limits (CPU/memory)
Verify all services have healthchecks
Verify log rotation configured for Loki
Verify backup strategy for PostgreSQL (volume snapshots)
Verify Redis persistence configured (AOF + RDB)
Verify Kafka replication factor > 1 (if multi-broker)
Verify RabbitMQ mirrored queues for HA
Verify TLS enabled for all external communication
Verify secrets management via external-secrets (not hardcoded)
Verify monitoring alerts configured in Prometheus Alertmanager
Verify runbooks exist for common failure scenarios
Verify disaster recovery plan documented
Verify rollback procedure documented
FULL PLATFORM VALIDATED — READY FOR PRODUCTION
How to Use This Plan
Work through sequentially — don't skip steps
When you find an issue — fix it immediately, then continue
Mark completed steps — track progress
Document findings — keep notes of issues found and fixed
Repeat phases — if Phase 1 fails, fix and re-run all Phase 1 steps
Quick Start Review Command
# Phase 1: Start platform
cd platform && docker compose up -d && docker compose ps

# Phase 2: Test gateway
curl http://localhost/health/order && curl http://localhost/health/payment

# Phase 3: Generate test traffic
for i in {1..10}; do curl -X POST http://localhost/orders -H "Content-Type: application/json" -d "{\"customer_id\":1,\"product_id\":1,\"quantity\":1,\"amount\":10.0}"; done

# Phase 4: Check observability
curl "http://localhost:3200/api/traces?service=order-service&operation=POST%20%2Forders"
curl "http://localhost:9090/api/v1/query?query=order_requests_total"
curl "http://localhost:3100/loki/api/v1/query_range?query={service=\"order-service\"}&limit=5"