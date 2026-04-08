"""Tests for the VCS adapter abstraction layer."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.adapters.git_credential import format_clone_url
from src.adapters.vcs_types import (
    CIStatus,
    CommitInfo,
    Discussion,
    FileDiff,
    Note,
    PullRequest,
)
from src.adapters.vcs_factory import create_vcs_client


# -- PullRequest model tests --------------------------------------------------


def test_pull_request_defaults():
    pr = PullRequest(
        repo_id=1,
        repo_path="owner/repo",
        pr_id=42,
        title="Test PR",
        source_branch="feature/test",
    )
    assert pr.repo_id == 1
    assert pr.repo_path == "owner/repo"
    assert pr.pr_id == 42
    assert pr.state == "open"
    assert pr.diffs == []
    assert pr.commits == []


def test_pull_request_full():
    pr = PullRequest(
        repo_id=1,
        repo_path="owner/repo",
        pr_id=42,
        title="Test",
        source_branch="feat",
        diffs=[
            FileDiff(old_path="a.py", new_path="a.py", diff="+line", new_file=True),
        ],
        discussions=[
            Discussion(
                id="d1",
                notes=[Note(author="u", body="text", created_at=datetime(2026, 1, 1))],
                resolved=True,
            )
        ],
        commits=[CommitInfo(sha="abc", title="msg")],
        ci_status="success",
    )
    assert len(pr.diffs) == 1
    assert pr.diffs[0].new_file is True
    assert len(pr.discussions) == 1
    assert pr.discussions[0].resolved is True


# -- MRAnalysisInput backward compatibility ------------------------------------


def test_mr_analysis_input_legacy_fields():
    from src.models.gitlab_types import MRAnalysisInput

    mr = MRAnalysisInput(
        project_id=99,
        project_path="group/svc",
        mr_iid=7,
        title="Legacy MR",
        source_branch="fix/x",
        pipeline_status="success",
    )
    # New field names
    assert mr.repo_id == 99
    assert mr.repo_path == "group/svc"
    assert mr.pr_id == 7
    assert mr.ci_status == "success"

    # Legacy property accessors
    assert mr.project_id == 99
    assert mr.project_path == "group/svc"
    assert mr.mr_iid == 7
    assert mr.pipeline_status == "success"


# -- CIStatus enum tests ------------------------------------------------------


def test_ci_status_values():
    assert CIStatus.SUCCESS == "success"
    assert CIStatus.FAILURE == "failure"
    assert CIStatus.CANCELLED == "cancelled"
    assert CIStatus.UNKNOWN == "unknown"


# -- Credential formatter tests ------------------------------------------------


def test_format_clone_url_gitlab():
    url = format_clone_url("gitlab", "https://gitlab.com", "tok123", "group/repo")
    assert url == "https://oauth2:tok123@gitlab.com/group/repo.git"


def test_format_clone_url_github():
    url = format_clone_url("github", "https://github.com", "ghp_xyz", "owner/repo")
    assert url == "https://x-access-token:ghp_xyz@github.com/owner/repo.git"


def test_format_clone_url_gitlab_custom_host():
    url = format_clone_url("gitlab", "https://git.example.com", "tok", "g/r")
    assert url == "https://oauth2:tok@git.example.com/g/r.git"


def test_format_clone_url_strips_trailing_slash():
    url = format_clone_url("github", "https://github.com/", "tok", "o/r")
    assert url == "https://x-access-token:tok@github.com/o/r.git"


# -- Factory tests -------------------------------------------------------------


def test_factory_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported VCS provider"):
        create_vcs_client("bitbucket", "https://bb.com", "tok")


# -- GitHub Actions workflow pattern in classifier -----------------------------


def test_github_workflow_pattern_matched():
    from src.services.classifier import filter_relevant_diffs

    diffs = [
        FileDiff(
            old_path=".github/workflows/ci.yml",
            new_path=".github/workflows/ci.yml",
            diff="+step",
        ),
    ]
    result = filter_relevant_diffs(diffs)
    assert len(result) == 1


def test_gitlab_ci_pattern_still_matched():
    from src.services.classifier import filter_relevant_diffs

    diffs = [
        FileDiff(old_path=".gitlab-ci.yml", new_path=".gitlab-ci.yml", diff="+stage"),
    ]
    result = filter_relevant_diffs(diffs)
    assert len(result) == 1
