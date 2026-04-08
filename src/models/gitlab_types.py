"""Backward-compatibility shim — re-exports from ``src.adapters.vcs_types``.

New code should import directly from ``src.adapters.vcs_types`` instead.
``MRAnalysisInput`` is an alias for ``PullRequest`` with field aliases to
keep existing callers working.
"""

from __future__ import annotations

from src.adapters.vcs_types import (
    CommitInfo,
    Discussion,
    FileDiff,
    Note,
    PullRequest,
)

__all__ = [
    "CommitInfo",
    "Discussion",
    "FileDiff",
    "MRAnalysisInput",
    "Note",
]


class MRAnalysisInput(PullRequest):
    """Legacy alias.  Accepts both old and new field names."""

    model_config = {"populate_by_name": True}

    # Accept legacy field names via __init__ override
    def __init__(self, **data):
        # Map legacy field names → new field names
        if "project_id" in data and "repo_id" not in data:
            data["repo_id"] = data.pop("project_id")
        if "project_path" in data and "repo_path" not in data:
            data["repo_path"] = data.pop("project_path")
        if "mr_iid" in data and "pr_id" not in data:
            data["pr_id"] = data.pop("mr_iid")
        if "pipeline_status" in data and "ci_status" not in data:
            data["ci_status"] = data.pop("pipeline_status")
        super().__init__(**data)

    # Expose legacy property names for reading
    @property
    def project_id(self) -> int:
        return self.repo_id

    @property
    def project_path(self) -> str:
        return self.repo_path

    @property
    def mr_iid(self) -> int:
        return self.pr_id

    @property
    def pipeline_status(self) -> str:
        return self.ci_status
