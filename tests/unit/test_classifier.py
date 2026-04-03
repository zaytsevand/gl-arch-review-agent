from src.models.classification import (
    Confidence,
    PerspectiveResult,
    Significance,
    SignificanceClassification,
    ChangeType,
)
from src.models.gitlab_types import FileDiff, MRAnalysisInput
from src.services.classifier import (
    aggregate_perspectives,
    build_user_message,
    filter_relevant_diffs,
)


def test_filter_relevant_diffs_keeps_controllers():
    diffs = [
        FileDiff(old_path="OrderController.java", new_path="OrderController.java", diff="+code"),
        FileDiff(old_path="README.md", new_path="README.md", diff="+docs"),
        FileDiff(old_path="application.yml", new_path="application.yml", diff="+config"),
    ]
    result = filter_relevant_diffs(diffs)
    assert len(result) == 2
    assert result[0].new_path == "OrderController.java"
    assert result[1].new_path == "application.yml"


def test_filter_relevant_diffs_keeps_entities():
    diffs = [
        FileDiff(old_path="src/model/Order.java", new_path="src/model/Order.java", diff="+entity"),
        FileDiff(old_path="test/OrderTest.java", new_path="test/OrderTest.java", diff="+test"),
    ]
    result = filter_relevant_diffs(diffs)
    assert len(result) == 1
    assert "model" in result[0].new_path


def test_filter_relevant_diffs_keeps_build_files():
    diffs = [
        FileDiff(old_path="build.gradle.kts", new_path="build.gradle.kts", diff="+dep"),
        FileDiff(old_path=".gitlab-ci.yml", new_path=".gitlab-ci.yml", diff="+stage"),
    ]
    result = filter_relevant_diffs(diffs)
    assert len(result) == 2


def test_filter_relevant_diffs_empty_input():
    assert filter_relevant_diffs([]) == []


def test_filter_relevant_diffs_no_matches():
    diffs = [
        FileDiff(old_path="README.md", new_path="README.md", diff="+text"),
        FileDiff(old_path="LICENSE", new_path="LICENSE", diff="+mit"),
    ]
    result = filter_relevant_diffs(diffs)
    assert len(result) == 0


def _make_perspective(
    name: str,
    sig: Significance,
    conf: Confidence = Confidence.HIGH,
    change_type: ChangeType = ChangeType.API_CHANGE,
) -> PerspectiveResult:
    return PerspectiveResult(
        perspective=name,
        classification=SignificanceClassification(
            significance=sig,
            change_type=change_type,
            confidence=conf,
            summary="test",
            rationale="test rationale",
            affected_services=["svc"],
        ),
    )


def test_aggregate_full_consensus():
    perspectives = [
        _make_perspective("api", Significance.HIGH),
        _make_perspective("dep", Significance.HIGH),
        _make_perspective("risk", Significance.HIGH),
    ]
    review = aggregate_perspectives(perspectives)
    assert review.consensus is True
    assert review.consensus_significance == Significance.HIGH
    assert review.consensus_confidence == Confidence.HIGH
    assert review.escalation_triggered is False


def test_aggregate_majority_consensus():
    perspectives = [
        _make_perspective("api", Significance.HIGH),
        _make_perspective("dep", Significance.HIGH),
        _make_perspective("risk", Significance.MODERATE),
    ]
    review = aggregate_perspectives(perspectives)
    assert review.consensus is True
    assert review.consensus_significance == Significance.HIGH


def test_aggregate_no_consensus():
    perspectives = [
        _make_perspective("api", Significance.HIGH),
        _make_perspective("dep", Significance.MODERATE),
        _make_perspective("risk", Significance.NON_SIGNIFICANT),
    ]
    review = aggregate_perspectives(perspectives)
    assert review.consensus is False
    assert review.escalation_triggered is True


def test_aggregate_borderline_confidence_propagates():
    perspectives = [
        _make_perspective("api", Significance.MODERATE, Confidence.HIGH),
        _make_perspective("dep", Significance.MODERATE, Confidence.BORDERLINE),
        _make_perspective("risk", Significance.MODERATE, Confidence.HIGH),
    ]
    review = aggregate_perspectives(perspectives)
    assert review.consensus is True
    # With weighted aggregation: 2 HIGH (3) + 1 BORDERLINE (1) = avg 2.33 → MEDIUM
    assert review.consensus_confidence == Confidence.MEDIUM


def test_build_user_message_includes_mr_metadata(significant_mr):
    relevant = filter_relevant_diffs(significant_mr.diffs)
    msg = build_user_message(significant_mr, relevant)
    assert "PLAT-034" in msg
    assert "order-service" in msg
    assert "feature/PLAT-034" in msg


def test_build_user_message_includes_discussions(significant_mr):
    relevant = filter_relevant_diffs(significant_mr.diffs)
    msg = build_user_message(significant_mr, relevant)
    assert "RESOLVED" in msg
    assert "RefundRequest" in msg


def test_build_user_message_includes_commits(significant_mr):
    relevant = filter_relevant_diffs(significant_mr.diffs)
    msg = build_user_message(significant_mr, relevant)
    assert "35765c1" in msg


def test_diff_truncation_adds_marker():
    """Truncated diffs should include a marker indicating omitted content."""
    long_diff = "+" + "x" * 3000  # over MAX_DIFF_CHARS
    diffs = [
        FileDiff(
            old_path="OrderController.java",
            new_path="OrderController.java",
            diff=long_diff,
        )
    ]
    msg = build_user_message(
        MRAnalysisInput(
            project_id=1, project_path="g/s", mr_iid=1,
            title="test", source_branch="f", diffs=diffs, commits=[],
        ),
        diffs,
    )
    assert "truncated" in msg
    assert "additional chars omitted" in msg


def test_aggregate_weighted_confidence_all_high():
    """3 HIGH-confidence votes → HIGH."""
    perspectives = [
        _make_perspective("api", Significance.HIGH, Confidence.HIGH),
        _make_perspective("dep", Significance.HIGH, Confidence.HIGH),
        _make_perspective("risk", Significance.HIGH, Confidence.HIGH),
    ]
    review = aggregate_perspectives(perspectives)
    assert review.consensus_confidence == Confidence.HIGH


def test_aggregate_weighted_confidence_all_borderline():
    """3 BORDERLINE votes → BORDERLINE."""
    perspectives = [
        _make_perspective("api", Significance.MODERATE, Confidence.BORDERLINE),
        _make_perspective("dep", Significance.MODERATE, Confidence.BORDERLINE),
        _make_perspective("risk", Significance.MODERATE, Confidence.BORDERLINE),
    ]
    review = aggregate_perspectives(perspectives)
    assert review.consensus_confidence == Confidence.BORDERLINE


def test_aggregate_weighted_two_high_one_medium():
    """2 HIGH + 1 MEDIUM → HIGH (avg 2.67)."""
    perspectives = [
        _make_perspective("api", Significance.MODERATE, Confidence.HIGH),
        _make_perspective("dep", Significance.MODERATE, Confidence.HIGH),
        _make_perspective("risk", Significance.MODERATE, Confidence.MEDIUM),
    ]
    review = aggregate_perspectives(perspectives)
    assert review.consensus_confidence == Confidence.HIGH
