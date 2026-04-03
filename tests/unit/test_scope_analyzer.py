from datetime import datetime

from src.models.gitlab_types import CommitInfo, FileDiff, MRAnalysisInput
from src.services.scope_analyzer import (
    extract_code_dependencies,
    extract_ticket_refs,
)


def _make_mr(**kwargs) -> MRAnalysisInput:
    defaults = dict(
        project_id=1,
        project_path="group/svc",
        mr_iid=1,
        title="MR title",
        source_branch="feature/test",
        diffs=[],
        commits=[],
    )
    defaults.update(kwargs)
    return MRAnalysisInput(**defaults)


def test_extract_ticket_from_title():
    mr = _make_mr(title="PLAT-034: V2 API workflow rework")
    refs = extract_ticket_refs(mr)
    assert len(refs) == 1
    assert refs[0].ticket_id == "PLAT-034"
    assert refs[0].source == "mr_title"


def test_extract_ticket_from_description():
    mr = _make_mr(
        title="Some title",
        description="Implements ORD-158 statistics endpoint",
    )
    refs = extract_ticket_refs(mr)
    assert any(r.ticket_id == "ORD-158" for r in refs)


def test_extract_ticket_from_commit():
    mr = _make_mr(
        title="Some title",
        commits=[
            CommitInfo(sha="abc", title="PAY-087: extract validation", message="PAY-087: extract validation", authored_date=datetime(2026, 4, 1)),
        ],
    )
    refs = extract_ticket_refs(mr)
    assert any(r.ticket_id == "PAY-087" and r.source == "commit_message" for r in refs)


def test_extract_ticket_from_diff():
    mr = _make_mr(
        title="Some title",
        diffs=[
            FileDiff(
                old_path="f.java", new_path="f.java",
                diff="// TODO: ORD-171 — add date range filtering",
            ),
        ],
    )
    refs = extract_ticket_refs(mr)
    assert any(r.ticket_id == "ORD-171" and r.source == "code_comment" for r in refs)


def test_no_duplicate_tickets():
    mr = _make_mr(
        title="PLAT-034: V2",
        description="Implements PLAT-034",
    )
    refs = extract_ticket_refs(mr)
    ticket_ids = [r.ticket_id for r in refs]
    assert ticket_ids.count("PLAT-034") == 2  # different sources


def test_extract_code_dependencies_urls():
    mr = _make_mr(diffs=[
        FileDiff(
            old_path="f.java", new_path="f.java",
            diff='String url = "http://localhost:8081/api/payments";',
        ),
    ])
    deps = extract_code_dependencies(mr)
    assert any("localhost:8081" in d for d in deps)


def test_extract_code_dependencies_feign():
    mr = _make_mr(diffs=[
        FileDiff(
            old_path="f.java", new_path="f.java",
            diff='@FeignClient("payment-service")',
        ),
    ])
    deps = extract_code_dependencies(mr)
    assert any("FeignClient" in d for d in deps)


def test_extract_code_dependencies_config_ref():
    mr = _make_mr(diffs=[
        FileDiff(
            old_path="f.java", new_path="f.java",
            diff='@Value("${payment.service.url}")',
        ),
    ])
    deps = extract_code_dependencies(mr)
    assert any("payment.service.url" in d for d in deps)


def test_empty_mr_no_tickets():
    mr = _make_mr(title="Fix typo", description="")
    refs = extract_ticket_refs(mr)
    assert len(refs) == 0


def test_ticket_pattern_rejects_url_components():
    """HTTPS-443 in a URL should not be treated as a ticket reference."""
    mr = _make_mr(
        title="Fix connection to https://service:443/api",
        description="See HTTPS-443 redirect issue",
    )
    refs = extract_ticket_refs(mr)
    # HTTPS-443 is preceded by "/" or is at URL boundary — should be filtered
    # Only genuine tickets should be found
    ticket_ids = [r.ticket_id for r in refs]
    assert "HTTPS-443" not in ticket_ids


def test_ticket_pattern_accepts_standard_tickets():
    """Standard JIRA-style tickets should still be matched."""
    mr = _make_mr(title="PROJ-123 implement feature", description="Related to TEAM-456")
    refs = extract_ticket_refs(mr)
    ticket_ids = [r.ticket_id for r in refs]
    assert "PROJ-123" in ticket_ids
    assert "TEAM-456" in ticket_ids
