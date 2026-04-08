"""GitHub VCS adapter — implements ``VCSClient`` using PyGithub."""

from __future__ import annotations

from src.adapters.vcs_client import VCSClient
from src.adapters.vcs_types import (
    CIStatus,
    CommitInfo,
    Discussion,
    FileDiff,
    Note,
    PullRequest,
)

try:
    from github import Github, GithubException
except ImportError:  # pragma: no cover
    Github = None  # type: ignore[assignment, misc]
    GithubException = Exception  # type: ignore[assignment, misc]

_GITHUB_STATUS_MAP: dict[str, CIStatus] = {
    "success": CIStatus.SUCCESS,
    "failure": CIStatus.FAILURE,
    "error": CIStatus.FAILURE,
    "cancelled": CIStatus.CANCELLED,
    "pending": CIStatus.PENDING,
    "action_required": CIStatus.PENDING,
    "neutral": CIStatus.SUCCESS,
    "skipped": CIStatus.CANCELLED,
    "timed_out": CIStatus.FAILURE,
    "stale": CIStatus.UNKNOWN,
}


class GitHubAdapter(VCSClient):
    def __init__(self, url: str, token: str):
        if Github is None:
            raise RuntimeError(
                "PyGithub is not installed. Install it with: pip install 'adr-agent[github]'"
            )
        self.url = url
        self.token = token
        base_url = None
        if url and "github.com" not in url:
            base_url = url.rstrip("/") + "/api/v3"
        self.gh = Github(login_or_token=token, base_url=base_url) if base_url else Github(login_or_token=token)

    # -- VCSClient implementation -------------------------------------------

    def authenticate(self) -> None:
        _ = self.gh.get_user().login

    def get_pull_request(self, repo_path: str, pr_id: int) -> PullRequest:
        repo = self.gh.get_repo(repo_path)
        pr = repo.get_pull(pr_id)

        diffs: list[FileDiff] = []
        for f in pr.get_files():
            diffs.append(
                FileDiff(
                    old_path=f.previous_filename or f.filename,
                    new_path=f.filename,
                    diff=f.patch or "",
                    new_file=f.status == "added",
                    deleted_file=f.status == "removed",
                    renamed_file=f.status == "renamed",
                )
            )

        discussions: list[Discussion] = []
        for comment in pr.get_review_comments():
            discussions.append(
                Discussion(
                    id=str(comment.id),
                    notes=[
                        Note(
                            author=comment.user.login,
                            body=comment.body or "",
                            created_at=comment.created_at,
                        )
                    ],
                    file_path=comment.path,
                    line_number=comment.position,
                )
            )

        commits: list[CommitInfo] = []
        for c in pr.get_commits():
            commits.append(
                CommitInfo(
                    sha=c.sha,
                    title=c.commit.message.split("\n", 1)[0],
                    message=c.commit.message,
                    authored_date=c.commit.author.date,
                )
            )

        ci_status = ""
        head_sha = pr.head.sha
        try:
            combined = repo.get_commit(head_sha).get_combined_status()
            ci_status = combined.state
        except Exception:
            pass

        return PullRequest(
            repo_id=repo.id,
            repo_path=repo_path,
            pr_id=pr_id,
            title=pr.title,
            description=pr.body or "",
            source_branch=pr.head.ref,
            target_branch=pr.base.ref,
            state=pr.state,
            author=pr.user.login,
            diffs=diffs,
            discussions=discussions,
            ci_status=ci_status,
            commits=commits,
            web_url=pr.html_url,
        )

    def list_pull_requests(
        self, repo_path: str, state: str = "all"
    ) -> list[PullRequest]:
        repo = self.gh.get_repo(repo_path)
        prs = repo.get_pulls(state=state)
        return [self.get_pull_request(repo_path, pr.number) for pr in prs]

    def list_org_pull_requests(
        self, org_path: str, state: str = "all"
    ) -> list[PullRequest]:
        org = self.gh.get_organization(org_path)
        all_prs: list[PullRequest] = []
        for repo in org.get_repos():
            try:
                all_prs.extend(
                    self.list_pull_requests(repo.full_name, state)
                )
            except Exception:
                continue
        return all_prs

    def list_org_repos(self, org_path: str) -> list[str]:
        org = self.gh.get_organization(org_path)
        return [r.full_name for r in org.get_repos()]

    def post_comment(self, repo_path: str, pr_id: int, body: str) -> None:
        repo = self.gh.get_repo(repo_path)
        pr = repo.get_pull(pr_id)
        pr.create_issue_comment(body)

    def post_review_thread(
        self,
        repo_path: str,
        pr_id: int,
        body: str,
        file_path: str | None = None,
        line: int | None = None,
    ) -> None:
        repo = self.gh.get_repo(repo_path)
        pr = repo.get_pull(pr_id)

        if file_path and line:
            head_sha = pr.head.sha
            pr.create_review_comment(
                body=body,
                commit=repo.get_commit(head_sha),
                path=file_path,
                line=line,
            )
        else:
            pr.create_issue_comment(body)

    def get_ci_status(self, repo_path: str, ref: str) -> CIStatus:
        repo = self.gh.get_repo(repo_path)
        try:
            combined = repo.get_commit(ref).get_combined_status()
            return _GITHUB_STATUS_MAP.get(combined.state, CIStatus.UNKNOWN)
        except Exception:
            return CIStatus.UNKNOWN

    def get_file_content(
        self, repo_path: str, file_path: str, ref: str = "main"
    ) -> str | None:
        repo = self.gh.get_repo(repo_path)
        try:
            content = repo.get_contents(file_path, ref=ref)
            if isinstance(content, list):
                return None
            return content.decoded_content.decode("utf-8")
        except Exception:
            return None
