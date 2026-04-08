"""GitLab VCS adapter — implements ``VCSClient`` using python-gitlab."""

from __future__ import annotations

import gitlab

from src.adapters.vcs_client import VCSClient
from src.adapters.vcs_types import (
    CIStatus,
    CommitInfo,
    Discussion,
    FileDiff,
    Note,
    PullRequest,
)

_GITLAB_STATUS_MAP: dict[str, CIStatus] = {
    "success": CIStatus.SUCCESS,
    "failed": CIStatus.FAILURE,
    "canceled": CIStatus.CANCELLED,
    "skipped": CIStatus.CANCELLED,
    "pending": CIStatus.PENDING,
    "running": CIStatus.RUNNING,
    "created": CIStatus.PENDING,
    "manual": CIStatus.PENDING,
}


class GitLabAdapter(VCSClient):
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self.gl = gitlab.Gitlab(url, private_token=token)

    # -- VCSClient implementation -------------------------------------------

    def authenticate(self) -> None:
        self.gl.auth()

    def get_pull_request(self, repo_path: str, pr_id: int) -> PullRequest:
        project = self.gl.projects.get(repo_path)
        mr = project.mergerequests.get(pr_id)

        diffs = [
            FileDiff(
                old_path=d["old_path"],
                new_path=d["new_path"],
                diff=d.get("diff", ""),
                new_file=d.get("new_file", False),
                deleted_file=d.get("deleted_file", False),
                renamed_file=d.get("renamed_file", False),
            )
            for d in mr.diffs.list(get_all=True)
        ]

        discussions = []
        for disc in mr.discussions.list(get_all=True):
            notes = [
                Note(
                    author=n["author"]["username"],
                    body=n["body"],
                    created_at=n["created_at"],
                    system=n.get("system", False),
                )
                for n in disc.attributes.get("notes", [])
            ]
            first_note = disc.attributes.get("notes", [{}])[0]
            position = first_note.get("position") or {}
            discussions.append(
                Discussion(
                    id=disc.id,
                    notes=notes,
                    resolved=disc.attributes.get("resolved", False),
                    file_path=position.get("new_path"),
                    line_number=position.get("new_line"),
                )
            )

        commits = [
            CommitInfo(
                sha=c.id,
                title=c.title,
                message=c.message,
                authored_date=c.authored_date,
            )
            for c in mr.commits()
        ]

        pipeline = mr.attributes.get("head_pipeline") or {}

        return PullRequest(
            repo_id=project.id,
            repo_path=repo_path,
            pr_id=pr_id,
            title=mr.title,
            description=mr.description or "",
            source_branch=mr.source_branch,
            target_branch=mr.target_branch,
            state=mr.state,
            author=mr.author["username"],
            diffs=diffs,
            discussions=discussions,
            ci_status=pipeline.get("status", ""),
            commits=commits,
            web_url=mr.web_url,
        )

    def list_pull_requests(
        self, repo_path: str, state: str = "all"
    ) -> list[PullRequest]:
        project = self.gl.projects.get(repo_path)
        mrs = project.mergerequests.list(state=state, get_all=True)
        return [self.get_pull_request(repo_path, mr.iid) for mr in mrs]

    def list_org_pull_requests(
        self, org_path: str, state: str = "all"
    ) -> list[PullRequest]:
        group = self.gl.groups.get(org_path)
        projects = group.projects.list(get_all=True)
        all_prs: list[PullRequest] = []
        for proj in projects:
            try:
                all_prs.extend(
                    self.list_pull_requests(proj.path_with_namespace, state)
                )
            except gitlab.exceptions.GitlabError:
                continue
        return all_prs

    def list_org_repos(self, org_path: str) -> list[str]:
        group = self.gl.groups.get(org_path)
        return [p.path_with_namespace for p in group.projects.list(get_all=True)]

    def post_comment(self, repo_path: str, pr_id: int, body: str) -> None:
        project = self.gl.projects.get(repo_path)
        mr = project.mergerequests.get(pr_id)
        mr.notes.create({"body": body})

    def post_review_thread(
        self,
        repo_path: str,
        pr_id: int,
        body: str,
        file_path: str | None = None,
        line: int | None = None,
    ) -> None:
        project = self.gl.projects.get(repo_path)
        mr = project.mergerequests.get(pr_id)

        if file_path and line:
            diff_refs = mr.attributes.get("diff_refs", {})
            mr.discussions.create(
                {
                    "body": body,
                    "position": {
                        "base_sha": diff_refs.get("base_sha", ""),
                        "start_sha": diff_refs.get("start_sha", ""),
                        "head_sha": diff_refs.get("head_sha", ""),
                        "position_type": "text",
                        "new_path": file_path,
                        "new_line": line,
                    },
                }
            )
        else:
            mr.notes.create({"body": body})

    def get_ci_status(self, repo_path: str, ref: str) -> CIStatus:
        project = self.gl.projects.get(repo_path)
        pipelines = project.pipelines.list(ref=ref, per_page=1)
        if pipelines:
            raw = pipelines[0].status
            return _GITLAB_STATUS_MAP.get(raw, CIStatus.UNKNOWN)
        return CIStatus.UNKNOWN

    def get_file_content(
        self, repo_path: str, file_path: str, ref: str = "main"
    ) -> str | None:
        project = self.gl.projects.get(repo_path)
        try:
            f = project.files.get(file_path=file_path, ref=ref)
            return f.decode().decode("utf-8")
        except gitlab.exceptions.GitlabGetError:
            return None
