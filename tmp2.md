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


In Python, interfaces are commonly represented using ABC + @abstractmethod
1. Normal class = implementation
2. Abstract class = interface/contract
                BUSINESS LAYER
                     │
                     ▼
              OrderRepository
              ┌─────────────┐
              │ create()    │
              │ get_all()   │
              │ get_by_id() │
              └─────────────┘
                     ▲
                     │
                INFRASTRUCTURE
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
PostgresOrderRepository     FakeOrderRepository
        │                         │
        ▼                         ▼
   PostgreSQL                  Tests

   if you're following Clean Architecture / Hexagonal Architecture / Dependency Inversion.
   The business/service layer should depend on abstractions, not concrete infrastructure implementations.
   class OrderService:
        def __init__(self, repository: OrderRepository):
            self.repository = repository

    not this

    class OrderService:
        def __init__(self, repository: PostgresOrderRepository):
            self.repository = repository

But there's an important exception:-
A service doesn't need an interface just because it's a service.

Good rule:-
Use an abstraction when the service depends on something that you may want to replace, mock, or isolate: