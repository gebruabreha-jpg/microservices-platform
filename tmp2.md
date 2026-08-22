Data Flow Verified
Order creation:

Client → NGINX → order-service (POST /orders)
order-service → PostgreSQL (INSERT INTO orders) ✅
order-service → Redis (SET order:<id>, DEL orders:list:*) ✅
order-service → Kafka (publish "orders" topic) ✅
Payment processing:

Kafka → payment-service (consume "orders" topic) ✅
payment-service → PostgreSQL (INSERT INTO payments) ✅
payment-service → RabbitMQ (queue "notifications") ✅
Notification dispatch:

RabbitMQ → notification-service (consume "notifications" queue) ✅
notification-service → PostgreSQL (INSERT INTO notifications) ✅
On failure → RabbitMQ DLQ (dlx exchange → dlq queue) ✅