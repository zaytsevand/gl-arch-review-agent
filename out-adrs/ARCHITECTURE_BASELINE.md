# Architecture Baseline

**Generated:** 2026-04-03  
**Agent:** ADR Review Agent v1.0  
**Repositories scanned:**
- `order-service` (branch: `main`)
- `payment-service` (branch: `main`)

---

## 1. Service Inventory

| Service | Port | Framework | Java | Build | Database | CI Image |
|---------|------|-----------|------|-------|----------|----------|
| order-service | 8080 | Spring Boot 3.2.3 | 21 | Gradle 8.5 (Kotlin DSL) | H2 in-memory (`testdb`) | `gradle:8.5-jdk21` |
| payment-service | 8081 | Spring Boot 3.2.3 | 21 | Gradle 8.5 (Kotlin DSL) | H2 in-memory (`paymentdb`) | `gradle:8.5-jdk21` |

---

## 2. order-service

### 2.1 Endpoints

| Method | Path | Description | Controller |
|--------|------|-------------|------------|
| POST | `/api/orders` | Create a new order (triggers payment initiation) | `OrderController` |
| GET | `/api/orders/{id}` | Retrieve order by ID | `OrderController` |
| GET | `/api/orders` | List all orders | `OrderController` |

### 2.2 Entities

**Order** (`orders` table)

| Field | Type | Constraints |
|-------|------|-------------|
| id | Long | PK, auto-generated |
| customerName | String | NOT NULL |
| productName | String | NOT NULL |
| quantity | Integer | NOT NULL |
| totalPrice | BigDecimal | NOT NULL |
| status | String | NOT NULL, default `"CREATED"` |
| createdAt | LocalDateTime | NOT NULL, set via `@PrePersist` |

**Order statuses (V1):** `CREATED`, `PAYMENT_INITIATED`, `PAYMENT_FAILED`

### 2.3 Repository

`OrderRepository` extends `JpaRepository<Order, Long>` -- no custom queries on main branch.

### 2.4 Services

| Class | Role |
|-------|------|
| `OrderService` | Core business logic: create order, initiate payment via PaymentClient, update order status based on payment result |
| `PaymentClient` | HTTP client using `RestTemplate` to call payment-service at `${payment.service.url}/api/payments` |

### 2.5 DTOs

| DTO | Fields | Usage |
|-----|--------|-------|
| `CreateOrderRequest` | customerName, productName, quantity, totalPrice | Inbound: order creation |
| `PaymentRequest` | orderId, amount | Outbound: sent to payment-service |
| `PaymentResponse` | id, orderId, status | Inbound: received from payment-service |

### 2.6 Configuration

- `AppConfig`: defines `RestTemplate` bean
- `application.yml`: H2 datasource, JPA with `ddl-auto: update`, payment service URL (`http://localhost:8081`)

### 2.7 Dependencies (build.gradle.kts)

- `spring-boot-starter-web`
- `spring-boot-starter-data-jpa`
- `h2` (runtime)
- `spring-boot-starter-test` (test)

### 2.8 CI Pipeline (.gitlab-ci.yml)

Stages: `build`, `test`  
- **build:** `gradle clean compileJava`  
- **test:** `gradle test`  
- Cache: `.gradle/caches`, `.gradle/wrapper`  
- Daemon disabled via `GRADLE_OPTS`

### 2.9 Test Coverage

Minimal -- only a Spring context load test (`OrderServiceApplicationTests`).

---

## 3. payment-service

### 3.1 Endpoints

| Method | Path | Description | Controller |
|--------|------|-------------|------------|
| POST | `/api/payments` | Create a new payment (simulated processing) | `PaymentController` |
| GET | `/api/payments/{id}` | Retrieve payment by ID | `PaymentController` |
| GET | `/api/payments/order/{orderId}` | Retrieve payment by order ID | `PaymentController` |

### 3.2 Entities

**Payment** (`payments` table)

| Field | Type | Constraints |
|-------|------|-------------|
| id | Long | PK, auto-generated |
| orderId | Long | NOT NULL |
| amount | BigDecimal | NOT NULL, precision 19 scale 2 |
| status | String | NOT NULL |
| paymentMethod | String | NOT NULL |
| createdAt | LocalDateTime | NOT NULL |

**Payment statuses (V1):** `PENDING`, `COMPLETED`

### 3.3 Repository

`PaymentRepository` extends `JpaRepository<Payment, Long>` with one custom method:
- `findByOrderId(Long orderId)` -- derived query

### 3.4 Services

| Class | Role |
|-------|------|
| `PaymentService` | Core logic: create payment, simulate processing (`Thread.sleep(100)`), set status to COMPLETED |

### 3.5 DTOs

| DTO | Fields | Usage |
|-----|--------|-------|
| `CreatePaymentRequest` | orderId, amount | Inbound: payment creation |
| `PaymentResponse` | id, orderId, amount, status, paymentMethod, createdAt | Outbound: API response |

### 3.6 Configuration

- `application.yml`: H2 datasource (`paymentdb`), JPA with `ddl-auto: update`, formatted SQL enabled, port 8081

### 3.7 Dependencies (build.gradle.kts)

- `spring-boot-starter-web`
- `spring-boot-starter-data-jpa`
- `h2` (runtime)
- `spring-boot-starter-test` (test)

### 3.8 CI Pipeline (.gitlab-ci.yml)

Identical to order-service: stages `build` and `test`, same Gradle image and cache config.

### 3.9 Test Coverage

Minimal -- only a Spring context load test (`PaymentServiceApplicationTests`).

---

## 4. Communication Patterns

### 4.1 Synchronous HTTP (REST)

| Caller | Callee | Protocol | Endpoint | Trigger |
|--------|--------|----------|----------|---------|
| order-service (`PaymentClient`) | payment-service | HTTP POST | `/api/payments` | Order creation |

- order-service uses `RestTemplate` (configured as a Spring bean in `AppConfig`)
- Target URL is externalized: `payment.service.url` property (defaults to `http://localhost:8081`)
- Error handling: exceptions are caught and swallowed; on failure, order is marked `PAYMENT_FAILED` instead of propagating the error
- No circuit breaker, retry, or timeout configuration

### 4.2 Data Flow

```
Client --> [POST /api/orders] --> order-service
              |
              |--> save Order (status=CREATED)
              |--> [POST /api/payments] --> payment-service
              |                               |
              |                               |--> save Payment (status=PENDING)
              |                               |--> simulate processing
              |                               |--> update Payment (status=COMPLETED)
              |                               |--> return PaymentResponse
              |
              |--> update Order status:
              |      SUCCESS --> PAYMENT_INITIATED
              |      FAILURE --> PAYMENT_FAILED
              |--> return Order
```

### 4.3 Asynchronous Communication

None on the main branch. All inter-service communication is synchronous HTTP.

---

## 5. Dependency Graph

```
                    +------------------+
                    |     Client       |
                    +--------+---------+
                             |
                   HTTP (REST API)
                             |
              +--------------+--------------+
              |                             |
    +---------v----------+       +----------v---------+
    |   order-service    |       |  payment-service   |
    |   (port 8080)      |       |   (port 8081)      |
    +---------+----------+       +--------------------+
              |                             ^
              |   HTTP POST /api/payments   |
              +-----------------------------+
              |
    +---------v----------+       +--------------------+
    |  H2: testdb        |       |  H2: paymentdb     |
    |  (in-memory)       |       |  (in-memory)       |
    +--------------------+       +--------------------+
```

**Direction of dependency:** order-service depends on payment-service (unidirectional).  
**Coupling:** order-service has compile-time knowledge of payment-service's API contract via `PaymentRequest`/`PaymentResponse` DTOs and the URL structure.

---

## 6. Shared Patterns and Conventions

| Pattern | Details |
|---------|---------|
| Build system | Gradle with Kotlin DSL (`build.gradle.kts`) |
| Java version | 21 |
| Spring Boot version | 3.2.3 |
| Dependency management | `io.spring.dependency-management` 1.1.4 |
| ORM | Spring Data JPA with Hibernate |
| Database | H2 in-memory (dev/test) |
| Schema management | `ddl-auto: update` (Hibernate auto-DDL) |
| DTO style | Java records |
| Entity style | Traditional POJO with explicit getters/setters (no Lombok) |
| Error handling | No global exception handling (`@ControllerAdvice`) in either service |
| Logging | `System.err.println` used in catch blocks (no SLF4J usage) |
| Tests | Spring context load tests only; no unit or integration tests |
| API versioning | Not present on main branch |
| Security | None (no authentication, no authorization, no CORS config) |
| Observability | None (no metrics, no tracing, no health endpoints beyond Boot defaults) |

---

## 7. Notable Gaps (Baseline)

1. **No input validation** -- neither service validates incoming request payloads
2. **No global error handling** -- no `@ControllerAdvice`; exceptions bubble up as 500s
3. **No test coverage** -- only context-load smoke tests exist
4. **No resilience patterns** -- no circuit breaker, retry, or timeout on inter-service calls
5. **System.err for error logging** -- not routed through SLF4J/Logback
6. **In-memory database** -- H2 only; no production database configuration
7. **No API documentation** -- no OpenAPI/Swagger configuration
8. **No security** -- endpoints are unauthenticated
