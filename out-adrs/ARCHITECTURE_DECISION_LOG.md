# Architecture Decision Log

This document tracks all architecturally significant changes across our microservices ecosystem.

| # | Date | Service | Change Type | Summary | Confidence | Rationale | ADR |
|---|------|---------|-------------|---------|------------|-----------|-----|
| 5 | 2026-04-03 | payment-service | New API / Cross-service contract | PLAT-034: V2 refund API (`/api/v2/payments/{id}/refund`), new `Refund` entity and `RefundService`; provides the refund endpoint consumed by order-service on cancellation | High | New entity, new API version, new cross-service contract -- establishes the payment side of the refund integration | [ADR-001](adr/001-api-v2-order-workflow-state-machine.md) |
| 4 | 2026-04-03 | order-service | New API / State machine / Cross-service integration | PLAT-034: V2 order workflow with state machine (`CREATED->CONFIRMED->PAID->SHIPPED->DELIVERED`, cancellation path), new `OrderWorkflowService`, cross-service refund call to payment-service | High | New API version, new architectural pattern (state machine), new cross-service dependency (refund) -- fundamentally changes the order lifecycle model | [ADR-001](adr/001-api-v2-order-workflow-state-machine.md) |
| 3 | 2026-04-03 | payment-service | New infrastructure / Communication pattern | PAY-095: WebSocket support for real-time payment status notifications; adds `spring-boot-starter-websocket`, `WebSocketConfig`, handler, and notification service layer (currently unwired -- dead code) | Medium | Introduces a new communication protocol (WebSocket) and a new dependency; however, the notification pipeline is not yet integrated into the payment flow | [ADR-002](adr/002-websocket-payment-notifications.md) |
| 2 | 2026-04-03 | payment-service | Refactoring / Design pattern | PAY-087: Extract payment validation into dedicated `PaymentValidator` component; separates validation concern from `PaymentService` | -- | Internal refactoring with no API or schema change; moderate significance as it establishes a validation pattern (reviewer suggested interface extraction for future composite validators) | -- |
| 1 | 2026-04-03 | order-service | New endpoint / Query layer | ORD-158: Add `/api/orders/statistics` endpoint with `OrderStatisticsResponse`; new repository queries (`countByStatus`, `sumAllTotalPrice`) | -- | New read-only endpoint within existing API surface; no cross-service impact, no new dependencies, no schema change | -- |

<!-- New entries should be added above this line -->
