"""Platform-agnostic VCS data models.

These replace the GitLab-specific models in ``src/models/gitlab_types.py``.
The old module re-exports these types for backward compatibility.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class CIStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    PENDING = "pending"
    RUNNING = "running"
    UNKNOWN = "unknown"


class Note(BaseModel):
    author: str
    body: str
    created_at: datetime
    system: bool = False


class Discussion(BaseModel):
    id: str
    notes: list[Note]
    resolved: bool = False
    file_path: str | None = None
    line_number: int | None = None


class FileDiff(BaseModel):
    old_path: str
    new_path: str
    diff: str
    new_file: bool = False
    deleted_file: bool = False
    renamed_file: bool = False


class CommitInfo(BaseModel):
    sha: str
    title: str
    message: str = ""
    authored_date: datetime | None = None


class PullRequest(BaseModel):
    """Platform-agnostic pull/merge request model.

    ``pr_id`` is the numeric identifier (GitLab ``iid``, GitHub PR number).
    ``repo_path`` uses ``owner/repo`` format on both platforms.
    """

    repo_id: int
    repo_path: str
    pr_id: int
    title: str
    description: str = ""
    source_branch: str
    target_branch: str = "main"
    state: str = "open"
    author: str = ""
    diffs: list[FileDiff] = []
    discussions: list[Discussion] = []
    ci_status: str = ""
    commits: list[CommitInfo] = []
    web_url: str = ""
