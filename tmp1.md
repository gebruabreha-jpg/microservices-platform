Professional Platform Review: What's Not Complete
Tier 1 — Critical Functional Gaps
1. Prometheus metrics are not actually exposed
Services define Counter and Histogram objects using prometheus_client, but with an isolated custom CollectorRegistry() instead of the default registry. This means:

The /metrics endpoints (e.g., order-service line 29 in order_service.py) return a hardcoded JSON dict like {"service": "order-service"} — not Prometheus exposition format
Prometheus is configured to scrape service:8080, but there's no endpoint that calls prometheus_client.generate_latest()
All the Counter/Histogram objects are created but never scraped — they accumulate in memory and are discarded on restart
Fix: Use the default registry (from prometheus_client import Counter, Histogram) and register a proper /metrics route:

from prometheus_client import generate_latest
@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
2. Everything is synchronous despite async FastAPI
Despite the README claiming async, every layer is sync:

Layer	Actual	Should Be
Router handlers	def health() (sync)	async def health()
Service functions	def create_order() (sync)	async def create_order()
Database	psycopg2 (blocking)	asyncpg
Redis	redis (sync)	redis.asyncio
RabbitMQ	pika.BlockingConnection (blocking)	aio-pika
Kafka consumer	kafka-python (sync)	aiokafka
HTTP clients	requests (sync)	httpx.AsyncClient
FastAPI runs sync handlers in a threadpool, so the async event loop provides no benefit. Each concurrent request blocks a thread.

Fix: Convert all def → async def across routes, services, repositories, and core; switch libraries as indicated. Update tests from TestClient to httpx.AsyncClient.

3. Circuit breakers defined but never invoked
shared/circuit_breaker.py defines four breakers (redis_breaker, kafka_breaker, rabbitmq_breaker, postgres_breaker), and they're imported in each service's core/database.py, but:

def queue_rabbitmq_job(queue, message):
    if rabbitmq_breaker:           # ← always True (pybreaker always returns truthy)
        queue_rabbitmq_job_impl(queue, message)
    else:                          # ← dead branch
        queue_rabbitmq_job_impl(queue, message)
The breaker is imported and checked but never wraps the actual call. postgres_breaker is defined but never even imported in any service. The @retry decorator from tenacity is applied, but pybreaker circuit breakers are not.

Fix: Apply breakers with @circuit_breaker decorators or with breaker: context managers around the actual I/O calls.

4. No outbox pattern — events can be lost
order_service.py:create_order() (line 76): calls publish_kafka_event("orders", event) after conn.commit(). If Kafka fails after the DB commit, the order is saved but the payment service never learns about it → payment never created
payment_service.py:process_payment() (line 56): queues a RabbitMQ notification after conn.commit(). Same data loss risk
Fix: Write the event to an outbox table within the same DB transaction, then have a separate publisher process/polling mechanism read and dispatch from the outbox.

5. Idempotency is broken/missing
order_router.py (line 21-22): extracts X-Correlation-ID from headers and passes it to create_order(), but create_order() in order_service.py never checks whether an order with that correlation ID already exists
payment_service.py:process_payment(): checks for existing payment by order_id but this is weak — if the first payment attempt failed, it returns the old (failed) record
notification_router.py: no idempotency at all
Fix: Implement proper idempotency key handling — store and check idempotency keys in a dedicated table/Redis.

Tier 2 — Missing Platform Capabilities
6. Kubernetes manifests are all placeholder stubs
All 7 directories under kubernetes/ contain only a README.md placeholder:

Directory	Status
kubernetes/helm/	"Placeholder for helm Kubernetes configuration"
kubernetes/ingress/	"Placeholder for ingress Kubernetes configuration"
kubernetes/gateway-api/	"Placeholder for gateway-api Kubernetes configuration"
kubernetes/service-mesh/	"Placeholder for service-mesh Kubernetes configuration"
kubernetes/cert-manager/	"Placeholder for cert-manager Kubernetes configuration"
kubernetes/external-secrets/	"Placeholder for external-secrets Kubernetes configuration"
kubernetes/argocd/	"Placeholder for argocd Kubernetes configuration"
The README claims the platform demonstrates "service mesh configs, HPA, and pod disruption budgets" and references an infrastructure/terraform/ directory — neither exists.

Fix: Create actual K8s manifests (Deployments, Services, HPAs, PDBs), Helm charts, Gateway API configs, service mesh policies, cert-manager Issuers, external-secrets, and Argo CD Applications.

7. No authentication, authorization, or mTLS
All endpoints are publicly accessible
No API key, JWT, OAuth2, or mTLS between services
The README mentions checking authentication in the Postman section, but no auth middleware exists
Fix: Add auth middleware to FastAPI apps, configure nginx with JWT verification, set up mTLS for inter-service communication.

8. Rate limiting is configured but not applied to routes
All main.py files have:

limiter = Limiter(key_func=get_ipaddr, default_limits=["100/minute"])
But:

This is wrapped in try/except ImportError: pass — silently disabled if slowapi isn't installed
No @limiter.limit("100/minute") decorators on individual routes
The default limit only applies if the middleware is properly registered (it isn't — no app.middleware("http")(limiter) call)
Fix: Add @limiter.limit() decorators on routes, ensure slowapi is in requirements.txt, and register the middleware properly.

9. Loki log shipping is not configured
Loki is running, but:

No promtail, fluent-bit, or otel-collector filelog receiver to collect container logs
Services log via print() (JSON) in shared/logger.py, but nothing ships those logs to Loki
The otel-collector logs pipeline only accepts OTLP logs (receivers: [otlp]), which the services don't send
Fix: Add a filelog receiver to otel-collector or deploy promtail/fluent-bit to collect container stdout/stderr logs and ship to Loki.

10. OTEL collector uses debug exporters everywhere
Both config.yaml and otel-collector-config.yaml export traces, metrics, and logs to debug only:

Traces → debug + OTLP to Tempo (✅ actually ships traces)
Metrics → debug only (❌ not shipped to Prometheus — but Prometheus scrapes services directly, which also doesn't work because /metrics returns JSON not Prometheus format)
Logs → debug only (❌ not shipped to Loki)
Fix: Configure the metrics exporter to push to Prometheus remote-write, or ensure services expose proper Prometheus-format metrics. Configure logs to ship to Loki.

11. Dead letter queue exists but no retry/backoff logic
notification_service.py has setup_dlq() and start_dlq_consumer(), and the rabbitmq definitions.json defines a notifications exchange and queue — but:

There are no retry queues or delayed retries
Failed messages go straight to DLQ with no retry attempt
The DLQ consumer just logs and acks — no dead-letter reprocessing or alerting
Fix: Implement exponential backoff retry queues before DLQ, and alert on DLQ depth.

12. No Grafana dashboards pre-built
grafana/provisioning/dashboards.yml points to /etc/grafana/dashboards/ directory, but no actual dashboard JSON files exist in platform/grafana/dashboards/.

Fix: Create dashboard JSON files for service metrics, Kafka lag, RabbitMQ queue depth, Redis cache hit ratio, PostgreSQL connection usage, etc.

Tier 3 — Code Quality & Correctness Issues
13. Duplicate metric registry in order_service.py
registry = CollectorRegistry()  # line 6 — first assignment
registry = CollectorRegistry()  # line 16 — overwrites, first is dead code
14. Silent exception swallowing in all background consumers
# payment_service.py:start_kafka_consumer()
while True:
    try:
        consumer = KafkaConsumer(...)
        for message in consumer:
            event = message.value
            create_payment_from_event(event)
    except Exception:
        pass  # ← all errors silently swallowed, no logging
Same pattern in notification_service.py:start_consumer() and start_dlq_consumer(). A consumer crash would silently loop forever with no restart logic, no logging, no alerting.

Fix: Log exceptions with correlation IDs, implement circuit breaker for consumer, add alerting on consumer health.

15. Inconsistent requirements management
shared-python-lib/requirements.txt only has:

fastapi, uvicorn, psycopg2-binary, redis, requests, opentelemetry-*, pydantic
Missing: pika, kafka-python, sqlalchemy, prometheus-client, tenacity, pybreaker, slowapi, alembic — which are in each service's own requirements.txt. This makes the shared lib's requirements misleading and incomplete.