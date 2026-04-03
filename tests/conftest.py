from __future__ import annotations

from datetime import datetime

import pytest

from src.models.gitlab_types import (
    CommitInfo,
    Discussion,
    FileDiff,
    MRAnalysisInput,
    Note,
)


@pytest.fixture
def trivial_mr() -> MRAnalysisInput:
    """ORD-142: Logging typos — non-significant."""
    return MRAnalysisInput(
        project_id=1,
        project_path="unlimit-test-agent/order-service",
        mr_iid=1,
        title="ORD-142: Fix logging typos and variable naming",
        description="Minor cosmetic fixes to logging and variable names.",
        source_branch="fix/ORD-142-logging-typos",
        target_branch="main",
        state="opened",
        author="mr.coder",
        diffs=[
            FileDiff(
                old_path="src/main/java/com/example/orderservice/service/OrderService.java",
                new_path="src/main/java/com/example/orderservice/service/OrderService.java",
                diff='@@ -20,7 +20,7 @@\n-        Order order = new Order(\n+        Order newOrder = new Order(\n',
            ),
            FileDiff(
                old_path="src/main/java/com/example/orderservice/controller/OrderController.java",
                new_path="src/main/java/com/example/orderservice/controller/OrderController.java",
                diff='@@ -17,6 +17,7 @@\n+    // REST API endpoint for order management\n',
            ),
        ],
        discussions=[
            Discussion(
                id="d1",
                notes=[
                    Note(
                        author="dr.review",
                        body="The comment on the constructor is misplaced.",
                        created_at=datetime(2026, 4, 1),
                    ),
                ],
                resolved=True,
                file_path="src/main/java/com/example/orderservice/controller/OrderController.java",
                line_number=18,
            ),
        ],
        pipeline_status="success",
        commits=[
            CommitInfo(
                sha="1fc504d",
                title="fix: rename local variable and update log message",
                authored_date=datetime(2026, 4, 1),
            ),
        ],
        web_url="https://gitlab.com/unlimit-test-agent/order-service/-/merge_requests/1",
    )


@pytest.fixture
def significant_mr() -> MRAnalysisInput:
    """PLAT-034: V2 API workflow rework — highly significant."""
    return MRAnalysisInput(
        project_id=1,
        project_path="unlimit-test-agent/order-service",
        mr_iid=3,
        title="PLAT-034: V2 API — Order workflow with state machine and cancellation",
        description="Implements V2 API with order workflow state machine, cancellation, and cross-service refund integration.",
        source_branch="feature/PLAT-034-api-v2-workflow-rework",
        target_branch="main",
        state="opened",
        author="mr.coder",
        diffs=[
            FileDiff(
                old_path="",
                new_path="src/main/java/com/example/orderservice/controller/OrderControllerV2.java",
                diff="@@ -0,0 +1,30 @@\n+@RestController\n+@RequestMapping(\"/api/v2/orders\")\n+public class OrderControllerV2 {\n",
                new_file=True,
            ),
            FileDiff(
                old_path="",
                new_path="src/main/java/com/example/orderservice/service/OrderWorkflowService.java",
                diff="@@ -0,0 +1,60 @@\n+public class OrderWorkflowService {\n+    public void transitionOrderStatus(...)\n",
                new_file=True,
            ),
            FileDiff(
                old_path="",
                new_path="src/main/java/com/example/orderservice/dto/RefundRequest.java",
                diff="@@ -0,0 +1,7 @@\n+public record RefundRequest(Long orderId, String reason) {}\n",
                new_file=True,
            ),
            FileDiff(
                old_path="src/main/java/com/example/orderservice/service/PaymentClient.java",
                new_path="src/main/java/com/example/orderservice/service/PaymentClient.java",
                diff="@@ -25,0 +26,15 @@\n+    public RefundResponse requestRefund(Long orderId) {\n",
            ),
        ],
        discussions=[
            Discussion(
                id="d1",
                notes=[
                    Note(
                        author="dr.review",
                        body="RefundRequest DTO has different fields across services. See DTO naming conventions.",
                        created_at=datetime(2026, 4, 1),
                    ),
                    Note(
                        author="mr.coder",
                        body="Will rename to OrderRefundRequest and coordinate with payment-service.",
                        created_at=datetime(2026, 4, 1),
                    ),
                ],
                resolved=True,
                file_path="src/main/java/com/example/orderservice/dto/RefundRequest.java",
                line_number=4,
            ),
            Discussion(
                id="d2",
                notes=[
                    Note(
                        author="dr.review",
                        body="No @Transactional on transitionOrderStatus(). Needs transactional boundaries.",
                        created_at=datetime(2026, 4, 1),
                    ),
                ],
                resolved=True,
            ),
        ],
        pipeline_status="success",
        commits=[
            CommitInfo(
                sha="35765c1",
                title="feat: implement API v2 with order workflow state machine",
                authored_date=datetime(2026, 4, 1),
            ),
        ],
        web_url="https://gitlab.com/unlimit-test-agent/order-service/-/merge_requests/3",
    )


@pytest.fixture
def moderate_mr() -> MRAnalysisInput:
    """PAY-087: Extract validation — moderate significance."""
    return MRAnalysisInput(
        project_id=2,
        project_path="unlimit-test-agent/payment-service",
        mr_iid=1,
        title="PAY-087: Extract payment validation to dedicated service",
        description="Refactors validation logic into a standalone PaymentValidator component.",
        source_branch="refactor/PAY-087-extract-validation",
        target_branch="main",
        state="opened",
        author="mr.coder",
        diffs=[
            FileDiff(
                old_path="",
                new_path="src/main/java/com/example/paymentservice/service/PaymentValidator.java",
                diff="@@ -0,0 +1,17 @@\n+@Component\n+public class PaymentValidator {\n+    public void validatePaymentRequest(CreatePaymentRequest request) {\n",
                new_file=True,
            ),
            FileDiff(
                old_path="src/main/java/com/example/paymentservice/service/PaymentService.java",
                new_path="src/main/java/com/example/paymentservice/service/PaymentService.java",
                diff="@@ -10,6 +10,8 @@\n+    private final PaymentValidator paymentValidator;\n",
            ),
        ],
        discussions=[],
        pipeline_status="success",
        commits=[
            CommitInfo(
                sha="a975912",
                title="refactor: extract validation logic into PaymentValidator",
                authored_date=datetime(2026, 4, 1),
            ),
        ],
        web_url="https://gitlab.com/unlimit-test-agent/payment-service/-/merge_requests/1",
    )
