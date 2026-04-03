from __future__ import annotations

import logging

import gitlab

from src.models.gitlab_types import (
    CommitInfo,
    Discussion,
    FileDiff,
    MRAnalysisInput,
    Note,
)

logger = logging.getLogger(__name__)


class GitLabClient:
    def __init__(self, url: str, token: str):
        self.gl = gitlab.Gitlab(url, private_token=token)
        self.gl.auth()

    def get_mr(self, project_path: str, mr_iid: int) -> MRAnalysisInput:
        project = self.gl.projects.get(project_path)
        mr = project.mergerequests.get(mr_iid)

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
            raw_notes = disc.attributes.get("notes", [])
            notes = []
            for n in raw_notes:
                try:
                    notes.append(
                        Note(
                            author=n.get("author", {}).get("username", "unknown"),
                            body=n.get("body", ""),
                            created_at=n.get("created_at", "1970-01-01T00:00:00Z"),
                            system=n.get("system", False),
                        )
                    )
                except (KeyError, TypeError) as exc:
                    logger.debug("Skipping malformed note in discussion %s: %s", disc.id, exc)
                    continue
            first_note = raw_notes[0] if raw_notes else {}
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

        return MRAnalysisInput(
            project_id=project.id,
            project_path=project_path,
            mr_iid=mr_iid,
            title=mr.title,
            description=mr.description or "",
            source_branch=mr.source_branch,
            target_branch=mr.target_branch,
            state=mr.state,
            author=mr.author["username"],
            diffs=diffs,
            discussions=discussions,
            pipeline_status=pipeline.get("status", "unknown"),
            commits=commits,
            web_url=mr.web_url,
        )

    def list_mrs(
        self, project_path: str, state: str = "all"
    ) -> list[MRAnalysisInput]:
        project = self.gl.projects.get(project_path)
        mrs = project.mergerequests.list(state=state, get_all=True)
        return [self.get_mr(project_path, mr.iid) for mr in mrs]

    def list_group_mrs(
        self, group_path: str, state: str = "all"
    ) -> list[MRAnalysisInput]:
        group = self.gl.groups.get(group_path)
        projects = group.projects.list(get_all=True)
        all_mrs: list[MRAnalysisInput] = []
        for proj in projects:
            try:
                all_mrs.extend(self.list_mrs(proj.path_with_namespace, state))
            except gitlab.exceptions.GitlabError as exc:
                logger.debug("Skipping project %s: %s", proj.path_with_namespace, exc)
                continue
        return all_mrs

    def post_mr_note(self, project_path: str, mr_iid: int, body: str) -> None:
        project = self.gl.projects.get(project_path)
        mr = project.mergerequests.get(mr_iid)
        mr.notes.create({"body": body})

    def post_mr_discussion(
        self,
        project_path: str,
        mr_iid: int,
        body: str,
        file_path: str | None = None,
        new_line: int | None = None,
    ) -> None:
        project = self.gl.projects.get(project_path)
        mr = project.mergerequests.get(mr_iid)

        if file_path and new_line:
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
                        "new_line": new_line,
                    },
                }
            )
        else:
            mr.notes.create({"body": body})

    def get_pipeline_status(self, project_path: str, ref: str) -> str:
        project = self.gl.projects.get(project_path)
        pipelines = project.pipelines.list(ref=ref, per_page=1)
        if pipelines:
            return pipelines[0].status
        return "unknown"

    def get_file_content(
        self, project_path: str, file_path: str, ref: str = "main"
    ) -> str | None:
        project = self.gl.projects.get(project_path)
        try:
            f = project.files.get(file_path=file_path, ref=ref)
            return f.decode().decode("utf-8")
        except gitlab.exceptions.GitlabGetError:
            return None
