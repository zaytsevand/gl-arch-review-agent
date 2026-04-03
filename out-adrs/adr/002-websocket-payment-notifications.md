# ADR-002: WebSocket Infrastructure for Real-Time Payment Status Notifications

**Date:** 2026-04-03  
**Status:** Proposed  
**Confidence:** Medium  
**Services:** payment-service  
**Source MR:** payment-service !2 (`feature/PAY-095-websocket-payment-notifications`)  
**Ticket:** PAY-095

## Context

Payment processing currently follows a request-response model: clients submit a payment and receive the final status in the HTTP response. There is no mechanism for clients to receive asynchronous notifications when a payment's status changes after the initial response (e.g., in a future flow where payments move through PENDING -> PROCESSING -> COMPLETED asynchronously, or when a refund is issued).

The team wants to introduce real-time push notifications so that frontend applications and other consumers can react immediately to payment status changes without polling.

## Decision

### 1. Add WebSocket support via Spring WebSocket

A new dependency `spring-boot-starter-websocket` is added to payment-service. A `WebSocketConfig` class implements `WebSocketConfigurer` and registers a handler at the `/ws/payment-status` endpoint.

### 2. Implement a raw WebSocket handler (not STOMP)

The implementation uses Spring's low-level `TextWebSocketHandler` rather than the higher-level STOMP protocol. `PaymentStatusWebSocketHandler` maintains a `CopyOnWriteArrayList<WebSocketSession>` of connected clients, adding sessions on connect and removing them on disconnect.

### 3. Introduce a notification service layer

`PaymentNotificationService` wraps the WebSocket handler and provides a `notifyPaymentStatusUpdate(String paymentId, String status)` method that other services can call. It catches `IOException` to prevent WebSocket failures from disrupting payment processing.

## Alternatives Considered

1. **STOMP over WebSocket with Spring Messaging** -- Would provide built-in topic-based subscription routing (e.g., `/topic/payments/{id}`), which would solve the broadcast-to-all problem out of the box. Rejected in favor of a simpler raw WebSocket approach for the prototype, but STOMP should be reconsidered if per-payment filtering becomes complex to maintain manually.

2. **Server-Sent Events (SSE)** -- Simpler than WebSocket for unidirectional server-to-client push. Would work well for this use case since the client only needs to receive updates, not send messages. Rejected because the team anticipated potential bidirectional needs (e.g., client-initiated subscription messages).

3. **Polling from the client** -- The simplest approach; clients periodically call `GET /api/payments/{id}` to check status. Rejected due to latency and unnecessary load at scale.

4. **Message broker with external push** -- Publish payment events to RabbitMQ/Kafka, consume with a dedicated notification service that pushes to clients. Overkill for current scale but would be the recommended path for production.

## Consequences

### Positive

- **Real-time capability:** Establishes the foundational infrastructure for push notifications in the payment domain.
- **Non-blocking architecture:** `PaymentNotificationService` catches exceptions, ensuring WebSocket failures never block payment processing.
- **Low coupling:** The notification service is a separate Spring bean; wiring it into the payment flow is a single method call.

### Negative / Risks

- **CRITICAL: Dead code -- notification pipeline is not wired.** `PaymentNotificationService` exists but `PaymentService.createPayment()` does not call it. No payment status changes currently trigger WebSocket notifications. The integration is deferred to avoid conflicting with PAY-087's changes to `PaymentService`. A follow-up ticket (PAY-103) is filed to complete the wiring.

- **Security: wildcard CORS origin.** `WebSocketConfig` sets `setAllowedOrigins("*")`, allowing any origin to connect to the WebSocket endpoint and receive payment data. Reviewer flagged this as a security concern. The developer agreed to restrict to known origins (`localhost:3000`, `localhost:8080`) for dev and parameterize via `application.yml` for production.

- **Privacy: broadcast to all clients.** `broadcastPaymentStatusUpdate()` sends every payment update to every connected WebSocket session, regardless of which payment the client is interested in. This is a data leakage issue -- Client A can see Client B's payment status changes. Reviewer recommended per-payment subscription filtering via a `Map<String, Set<WebSocketSession>>`.

- **Fragile JSON serialization.** JSON messages are constructed via `String.format()` instead of using Jackson's `ObjectMapper`. This does not handle special character escaping and will produce malformed JSON if paymentId or status contain characters like quotes or backslashes. Reviewer recommended switching to `ObjectMapper.writeValueAsString()`.

- **No structured logging.** Error handling in `PaymentNotificationService` uses `System.err.println` instead of SLF4J. This bypasses the logging framework, meaning errors will not appear in structured log output, log aggregation systems, or be filterable by log level.

- **At-most-once delivery.** If a WebSocket send fails (client disconnected, network issue), the notification is lost. There is no retry mechanism, no message queue, and no delivery guarantee. The developer documented this as a known limitation and filed PAY-103 for retry support.

- **No test coverage.** Neither the WebSocket handler nor the notification service have tests. The reviewer requested at minimum an integration test using `MockWebSocketSession`.

### Dead Code Inventory

| Class | Method | Status |
|-------|--------|--------|
| `PaymentNotificationService` | `notifyPaymentStatusUpdate()` | Never called -- no caller in the codebase |
| `PaymentStatusWebSocketHandler` | `broadcastPaymentStatusUpdate()` | Only called by `PaymentNotificationService` (which is itself dead code) |
| `PaymentStatusWebSocketHandler` | `handleTextMessage()` | Empty implementation -- no incoming message handling |

### Follow-up Items

| Item | Owner | Ticket |
|------|-------|--------|
| Wire `PaymentNotificationService` into `PaymentService` | payment-service | PAY-103 |
| Restrict WebSocket allowed origins | payment-service | PAY-095 (next push) |
| Per-payment subscription filtering | payment-service | PAY-095 (next push) |
| Replace String.format with ObjectMapper | payment-service | PAY-095 (next push) |
| Replace System.err with SLF4J logger | payment-service | PAY-095 (next push) |
| Add WebSocket integration tests | payment-service | PAY-095 (next push) |
| Evaluate STOMP migration for production | payment-service | TBD |
