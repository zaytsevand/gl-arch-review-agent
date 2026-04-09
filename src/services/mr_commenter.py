from __future__ import annotations

import re

from jinja2 import Environment, FileSystemLoader
from pathlib import Path

from src.models.classification import (
    Confidence,
    MultiAgentReview,
    Significance,
)
from src.adapters.vcs_types import PullRequest
from src.adapters.vcs_client import VCSClient

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _render_comment(comment_type: str, **kwargs) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("mr_comment.md.j2")
    return template.render(comment_type=comment_type, **kwargs)


def detect_doc_inconsistencies(mr: PullRequest) -> list[dict]:
    issues: list[dict] = []
    for diff in mr.diffs:
        if "README" in diff.new_path:
            if re.search(r"mvn\s+(clean|install|test|spring-boot:run)", diff.diff):
                has_gradle = any(
                    "gradle" in d.new_path.lower() or "build.gradle" in d.new_path.lower()
                    for d in mr.diffs
                )
                if has_gradle or "gradle" in mr.source_branch.lower():
                    issues.append(
                        {
                            "file_path": diff.new_path,
                            "message": "README references Maven commands but the project uses Gradle.",
                        }
                    )
    return issues


def post_feedback(
    mr: PullRequest,
    review: MultiAgentReview,
    vcs_client: VCSClient,
    adl_entry_number: int | None = None,
    adr_link: str | None = None,
) -> None:
    significance = review.consensus_significance
    if not significance:
        return

    if significance == Significance.NON_SIGNIFICANT:
        if review.consensus_confidence == Confidence.BORDERLINE:
            body = _render_comment(
                "borderline_skip",
                rationale=review.perspectives[0].classification.rationale
                if review.perspectives
                else "No significant architectural impact detected.",
            )
            vcs_client.post_comment(mr.repo_path, mr.pr_id, body)
        return

    first_cls = review.perspectives[0].classification if review.perspectives else None
    if not first_cls:
        return

    body = _render_comment(
        "summary",
        significance=significance.value,
        confidence=review.consensus_confidence.value if review.consensus_confidence else "medium",
        change_type=first_cls.change_type.value.replace("_", " ").title(),
        summary=first_cls.summary,
        adr_link=adr_link,
        adl_entry=adl_entry_number,
    )
    vcs_client.post_comment(mr.repo_path, mr.pr_id, body)

    doc_issues = detect_doc_inconsistencies(mr)
    for issue in doc_issues:
        quality_body = _render_comment("quality", summary=issue["message"])
        vcs_client.post_comment(mr.repo_path, mr.pr_id, quality_body)
