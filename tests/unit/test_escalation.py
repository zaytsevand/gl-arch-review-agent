from datetime import date

from src.models.classification import (
    ChangeType,
    Confidence,
    MultiAgentReview,
    PerspectiveResult,
    Significance,
    SignificanceClassification,
)
from src.models.state import EscalationPrecedent, ProcessingState
from src.services.escalation import (
    compute_pattern_hash,
    evaluate_escalation,
    format_escalation_comment,
)


def _make_review(
    sig: Significance = Significance.MODERATE,
    conf: Confidence = Confidence.HIGH,
    change_type: ChangeType = ChangeType.API_CHANGE,
    consensus: bool = True,
    files: list[str] | None = None,
) -> MultiAgentReview:
    cls = SignificanceClassification(
        significance=sig,
        change_type=change_type,
        confidence=conf,
        summary="test",
        rationale="test",
        affected_services=["svc"],
        relevant_files=files or ["file.java"],
    )
    return MultiAgentReview(
        perspectives=[PerspectiveResult(perspective="test", classification=cls)],
        consensus=consensus,
        consensus_significance=sig if consensus else None,
        consensus_confidence=conf,
        escalation_triggered=not consensus,
        escalation_reason="disagreement" if not consensus else None,
    )


def test_no_escalation_on_consensus():
    review = _make_review(consensus=True)
    state = ProcessingState()
    result = evaluate_escalation(review, state)
    assert result.escalation_triggered is False


def test_escalation_on_disagreement():
    review = _make_review(consensus=False)
    state = ProcessingState()
    result = evaluate_escalation(review, state)
    assert result.escalation_triggered is True
    assert "agent_disagreement" in result.escalation_reason


def test_escalation_on_security_change():
    review = _make_review(change_type=ChangeType.SECURITY, consensus=True)
    state = ProcessingState()
    result = evaluate_escalation(review, state)
    assert result.escalation_triggered is True
    assert "security_implication" in result.escalation_reason


def test_escalation_on_borderline_significant():
    review = _make_review(
        sig=Significance.HIGH,
        conf=Confidence.BORDERLINE,
        consensus=True,
    )
    state = ProcessingState()
    result = evaluate_escalation(review, state)
    assert result.escalation_triggered is True
    assert "unresolvable_ambiguity" in result.escalation_reason


def test_precedent_skips_escalation():
    review = _make_review(consensus=False, files=["OrderController.java"])
    pattern_hash = compute_pattern_hash(review)

    state = ProcessingState(
        escalation_precedents=[
            EscalationPrecedent(
                pattern_hash=pattern_hash,
                human_decision="moderate",
                resolved_date=date(2026, 4, 1),
                context_summary="test precedent",
            )
        ]
    )

    result = evaluate_escalation(review, state)
    assert result.escalation_triggered is False
    assert result.consensus is True
    assert result.consensus_significance == Significance.MODERATE


def test_pattern_hash_deterministic():
    review1 = _make_review(files=["a.java", "b.java"])
    review2 = _make_review(files=["b.java", "a.java"])
    assert compute_pattern_hash(review1) == compute_pattern_hash(review2)


def test_format_escalation_comment():
    review = _make_review(consensus=False)
    review.escalation_reason = "Agent disagreement"
    comment = format_escalation_comment(review)
    assert "Escalation Required" in comment
    assert "Agent Assessments" in comment
    assert "Action Required" in comment
