"""Abstract VCS client interface.

All platform adapters (GitLab, GitHub) implement this protocol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.adapters.vcs_types import CIStatus, PullRequest


class VCSClient(ABC):
    """Platform-agnostic VCS operations."""

    @abstractmethod
    def authenticate(self) -> None: ...

    @abstractmethod
    def get_pull_request(self, repo_path: str, pr_id: int) -> PullRequest: ...

    @abstractmethod
    def list_pull_requests(
        self, repo_path: str, state: str = "all"
    ) -> list[PullRequest]: ...

    @abstractmethod
    def list_org_pull_requests(
        self, org_path: str, state: str = "all"
    ) -> list[PullRequest]: ...

    @abstractmethod
    def list_org_repos(self, org_path: str) -> list[str]: ...

    @abstractmethod
    def post_comment(self, repo_path: str, pr_id: int, body: str) -> None: ...

    @abstractmethod
    def post_review_thread(
        self,
        repo_path: str,
        pr_id: int,
        body: str,
        file_path: str | None = None,
        line: int | None = None,
    ) -> None: ...

    @abstractmethod
    def get_ci_status(self, repo_path: str, ref: str) -> CIStatus: ...

    @abstractmethod
    def get_file_content(
        self, repo_path: str, file_path: str, ref: str = "main"
    ) -> str | None: ...
