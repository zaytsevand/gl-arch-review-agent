# ADR-001: API V2 Order Workflow with State Machine and Cross-Service Refund Integration

**Date:** 2026-04-03  
**Status:** Proposed  
**Confidence:** High  
**Services:** order-service, payment-service  
**Source MRs:** order-service !3 (`feature/PLAT-034-api-v2-workflow-rework`), payment-service !3 (`feature/PLAT-034-api-v2-workflow-rework`)  
**Ticket:** PLAT-034

## Context

The existing V1 order API has a simple lifecycle: orders are created, payment is initiated synchronously, and the order status becomes either `PAYMENT_INITIATED` or `PAYMENT_FAILED`. There is no support for confirming, shipping, delivering, or cancelling orders after creation. As the business grows, the team needs a richer order workflow that models real-world fulfillment stages and supports cancellation with automated refund processing.

The V1 API cannot be modified without breaking existing consumers, so a new V2 API namespace is being introduced alongside the existing V1 endpoints.

This change spans two services:
- **order-service** introduces a state machine governing order lifecycle transitions and a new V2 controller with confirm/cancel operations.
- **payment-service** introduces a `Refund` entity, a `RefundService`, and a V2 controller endpoint for processing refunds triggered by order cancellations.

The two services are now coupled through a new refund contract: when an order is cancelled in order-service, it calls `POST /api/v2/payments/{orderId}/refund` on payment-service.

## Decision

### 1. Introduce a V2 API namespace in both services

- order-service: `OrderControllerV2` mapped to `/api/v2/orders`
- payment-service: `PaymentControllerV2` mapped to `/api/v2/payments`
- V1 endpoints remain unchanged and operational

### 2. Implement an order state machine in order-service

A new `OrderWorkflowService` manages status transitions with explicit validation. The allowed transitions are:

```
CREATED --> CONFIRMED --> PAID --> SHIPPED --> DELIVERED
   |            |
   v            v
CANCELLED   CANCELLED
```

Invalid transitions are rejected with `IllegalStateException`. The transition table is implemented as a method-level `HashSet` check (with reviewer feedback to refactor to a static `Map<String, Set<String>>`).

Order status remains a `String` (not an enum) due to existing V1 database schema constraints. Migration to an enum is deferred to a follow-up ticket.

### 3. Cross-service refund integration on cancellation

When an order transitions to `CANCELLED`, order-service calls payment-service's new refund endpoint via `PaymentClient.requestRefund()`. Payment-service creates a `Refund` entity, records the refund amount (equal to the original payment amount), and updates the payment status to `REFUNDED`.

### 4. New Refund entity and repository in payment-service

A `Refund` JPA entity is introduced with fields: id, paymentId, amount, status, reason, createdAt. Persisted to the `refunds` table. `RefundRepository` provides lookup by paymentId.

## Alternatives Considered

1. **Extend V1 API with new statuses** -- Rejected because it would break existing API consumers and tightly couple the rollout of new workflow features to V1 compatibility.

2. **Event-driven refund processing (async)** -- Considered using a message broker (e.g., RabbitMQ) for order-service to publish a `OrderCancelled` event that payment-service subscribes to. Deferred due to the added infrastructure complexity; synchronous HTTP is acceptable for the current scale. The team may revisit this if reliability requirements increase.

3. **Enum-based order status** -- Preferred by reviewers but deferred because migrating the existing V1 string-based statuses in the database requires a data migration. Planned for a follow-up ticket.

4. **Saga pattern for cancel + refund** -- A distributed saga with compensation would provide stronger consistency guarantees. Considered overkill for the current prototype scope, but the transactional boundary concern (noted in review) signals this may be needed as the system matures.

## Consequences

### Positive

- **Clear lifecycle model:** The state machine makes valid order transitions explicit and prevents illegal state changes at the application level.
- **Backward compatible:** V1 API is untouched. V2 can be adopted incrementally by consumers.
- **Refund traceability:** Every refund is persisted with amount, reason, and timestamp, providing an audit trail.

### Negative / Risks

- **Cross-service coupling:** order-service now depends on payment-service's V2 refund endpoint. If payment-service is unavailable during cancellation, the refund silently fails (error is swallowed with `System.err.println`). This is a data consistency risk flagged by reviewers.
- **No transactional boundary:** `OrderWorkflowService.transitionOrderStatus()` lacks `@Transactional`. The order status may be updated even if the subsequent refund call fails. Reviewer recommended adding `@Transactional` and handling the refund call outside the transaction via an application event.
- **No idempotency on refunds:** Calling the refund endpoint twice creates duplicate refund records. Reviewer recommended adding a uniqueness check on `paymentId` in `RefundService` and a DB-level unique constraint.
- **Refund lifecycle skipped:** `RefundService.processRefund()` immediately sets status to `COMPLETED` without going through `PENDING` -> `PROCESSING` -> `COMPLETED`. The intermediate states are modeled in the entity but not enforced in the flow.
- **DTO naming collision:** Both services define a `RefundRequest` record with different fields (`orderId` vs `paymentId`). Reviewer recommended renaming to `OrderRefundRequest` and `PaymentRefundRequest` to avoid confusion.
- **Incomplete V2 surface:** The V2 controller only exposes `/confirm` and `/cancel`. Full CRUD and remaining transitions (PAID, SHIPPED, DELIVERED) are deferred to a follow-up MR.

### Follow-up Items

| Item | Owner | Ticket |
|------|-------|--------|
| Add `@Transactional` + event-based refund trigger | order-service | PLAT-034 (next push) |
| Refund idempotency check + DB unique constraint | payment-service | PLAT-034 (next push) |
| Rename cross-service DTOs per convention | both services | PLAT-034 (next push) |
| Full V2 order CRUD + remaining transitions | order-service | follow-up TBD |
| Refund lifecycle state machine (PENDING->PROCESSING->COMPLETED) | payment-service | follow-up TBD |
| Migrate order status from String to enum | order-service | follow-up TBD |
