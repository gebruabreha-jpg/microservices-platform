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