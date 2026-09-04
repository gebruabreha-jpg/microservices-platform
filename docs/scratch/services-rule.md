1,Direct imports (tight coupling)  or  No Dependency Injection so use  # DI container,  2,2,No Interfaces/Abstractions which Violates Dependency Inversion,
3,
The code follows procedural programming, not OOP. It needs:-
    Classes with proper encapsulation
    Interfaces/abstractions for dependencies
    Dependency injection container
    Remove global state
    Apply Dependency Inversion Principle
For enterprise scale, you'd need Clean Architecture + CQRS + full testing.

 
 
 1,Clean Architecture:-
 ┌─────────────────────────────────────────────────────────────┐
│                    Clean Architecture                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Domain Layer (Core)                     │    │
│  │  - Entities (Order, Notification)                   │    │
│  │  - Value Objects (Money, Address)                   │    │
│  │  - Domain Events (OrderCreatedEvent)                │    │
│  │  - Business Rules (validation, calculations)        │    │
│  │                                                      │    │
│  │  ← NO dependencies on database, framework, UI →     │    │
│  └─────────────────────────────────────────────────────┘    │
│                          ▲                                   │
│                          │ depends on                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Application Layer (Use Cases)              │    │
│  │  - Commands (CreateOrderCommand)                    │    │
│  │  - Queries (GetOrderQuery)                          │    │
│  │  - Interfaces (IOrderRepository)                    │    │
│  │  - DTOs (OrderResponse)                             │    │
│  └─────────────────────────────────────────────────────┘    │
│                          ▲                                   │
│                          │ implements                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │          Infrastructure Layer (External)             │    │
│  │  - Database (PostgresOrderRepository)               │    │
│  │  - Messaging (KafkaEventPublisher)                  │    │
│  │  - Cache (RedisCacheClient)                         │    │
│  │  - Framework (FastAPI, SQLAlchemy)                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘



2,CQRS:-
┌─────────────────────────────────────────────────────────────┐
│                        CQRS                                  │
│                                                              │
│  ┌─────────────────────┐    ┌─────────────────────┐         │
│  │     COMMANDS         │    │      QUERIES         │         │
│  │     (Write)          │    │      (Read)          │         │
│  │                      │    │                      │         │
│  │  CreateOrderCommand  │    │  GetOrderQuery       │         │
│  │  UpdateOrderCommand  │    │  ListOrdersQuery     │         │
│  │  DeleteOrderCommand  │    │  SearchOrdersQuery   │         │
│  │                      │    │                      │         │
│  │  → Changes state     │    │  → Returns data      │         │
│  │  → Returns void/ID   │    │  → No side effects   │         │
│  │  → Validates rules   │    │  → Can be cached     │         │
│  └─────────────────────┘    └─────────────────────┘         │
│              │                          │                    │
│              ▼                          ▼                    │
│  ┌─────────────────────┐    ┌─────────────────────┐         │
│  │   Command Handler    │    │   Query Handler      │         │
│  │   - Business logic   │    │   - Direct read      │         │
│  │   - Validation       │    │   - No business logic│         │
│  │   - Publish events   │    │   - Can use DTOs    │         │
│  └─────────────────────┘    └─────────────────────┘         │
│              │                          │                    │
│              ▼                          ▼                    │
│  ┌─────────────────────┐    ┌─────────────────────┐         │
│  │   Write Database     │    │   Read Database      │         │
│  │   (PostgreSQL)       │    │   (Redis/Read Replica│         │
│  └─────────────────────┘    └─────────────────────┘         │
│                                                              │
└─────────────────────────────────────────────────────────────┘



3,test:-
┌─────────────────────────────────────────────────────────────┐
│                    Testing Pyramid                            │
│                                                              │
│                        ╱╲                                   │
│                       ╱  ╲                                  │
│                      ╱ E2E╲                                 │
│                     ╱ Tests╲                                │
│                    ╱ (Few)  ╲                               │
│                   ╱──────────╲                              │
│                  ╱ Integration ╲                             │
│                 ╱    Tests      ╲                            │
│                ╱   (Some)        ╲                           │
│               ╱──────────────────╲                          │
│              ╱    Unit Tests       ╲                         │
│             ╱      (Many)          ╲                        │
│            ╱────────────────────────╲                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
DONE



Objective:-
Build a complete functional microservices platform (order, payment, notification services) with Clean Architecture, proper observability, resilience patterns, and DRY code organization

Important Details
    3 microservices + shared library + traffic generator + docker-compose infrastructure
    middleware/ and resilience/ are separate packages (not merged)
    shared/ contains observability only: tracing, metrics, logging
    shared/implementations/ contains all shared connection factories and implementations (DRY)
    resilience/ contains circuit_breaker.py and retry.py
    Health checks belong in main.py (not router) for K8s probes
    Service-specific metric names preferred: order_requests_total over http_requests_total
    Used get_metric() function name and metric variable name
    Repository files are separate modules (not deleted)
    Clean Architecture: Domain at core, dependencies point inward
    CQRS: Separate reads from writes
    Full testing: Unit + Integration + E2E test pyramid