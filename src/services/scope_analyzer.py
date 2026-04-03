from __future__ import annotations

import logging
import re
from pathlib import Path

import gitlab.exceptions

from src.models.classification import BlameEntry, ChangeScope, RelatedMR, TicketRef
from src.models.gitlab_types import MRAnalysisInput
from src.services.git_ops import GitOps
from src.services.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)

TICKET_PATTERN = re.compile(r"(?<![A-Za-z/])([A-Z]{2,10}-\d+)")


def extract_ticket_refs(mr: MRAnalysisInput) -> list[TicketRef]:
    refs: list[TicketRef] = []
    seen: set[tuple[str, str]] = set()

    def _add(ticket_id: str, source: str) -> None:
        key = (ticket_id, source)
        if key not in seen:
            seen.add(key)
            refs.append(
                TicketRef(
                    ticket_id=ticket_id,
                    source=source,
                    project_path=mr.project_path,
                )
            )

    for match in TICKET_PATTERN.findall(mr.title):
        _add(match, "mr_title")

    for match in TICKET_PATTERN.findall(mr.description):
        _add(match, "mr_description")

    for commit in mr.commits:
        for match in TICKET_PATTERN.findall(commit.message):
            _add(match, "commit_message")

    for diff in mr.diffs:
        for match in TICKET_PATTERN.findall(diff.diff):
            _add(match, "code_comment")

    return refs


def find_related_mrs(
    ticket_refs: list[TicketRef],
    current_mr: MRAnalysisInput,
    gitlab_client: GitLabClient,
    group_path: str,
) -> list[RelatedMR]:
    related: list[RelatedMR] = []
    ticket_ids = {ref.ticket_id for ref in ticket_refs}

    if not ticket_ids:
        return related

    group = gitlab_client.gl.groups.get(group_path)
    projects = group.projects.list(get_all=True)

    for project in projects:
        proj_path = project.path_with_namespace
        if proj_path == current_mr.project_path:
            continue

        try:
            proj = gitlab_client.gl.projects.get(proj_path)
            mrs = proj.mergerequests.list(state="all", per_page=50)
            for mr in mrs:
                for ticket_id in ticket_ids:
                    if ticket_id in (mr.title or "") or ticket_id in (
                        mr.description or ""
                    ):
                        related.append(
                            RelatedMR(
                                project_path=proj_path,
                                mr_iid=mr.iid,
                                title=mr.title,
                                shared_ticket=ticket_id,
                            )
                        )
                        break
        except gitlab.exceptions.GitlabError as exc:
            logger.debug("Skipping project %s: %s", proj_path, exc)
            continue

    return related


def extract_code_dependencies(mr: MRAnalysisInput) -> list[str]:
    deps: set[str] = set()

    for diff in mr.diffs:
        url_matches = re.findall(
            r"https?://[^\s\"']+|localhost:\d+", diff.diff
        )
        for url in url_matches:
            deps.add(url)

        feign_matches = re.findall(r"@FeignClient\([^)]*\)", diff.diff)
        for match in feign_matches:
            deps.add(f"FeignClient: {match}")

        service_url_matches = re.findall(
            r"\$\{([^}]*service[^}]*url[^}]*)\}", diff.diff, re.IGNORECASE
        )
        for match in service_url_matches:
            deps.add(f"Config: ${{{match}}}")

    return sorted(deps)


def run_blame_analysis(
    mr: MRAnalysisInput, git_ops: GitOps, repo_dir: Path
) -> list[BlameEntry]:
    entries: list[BlameEntry] = []

    for diff in mr.diffs:
        if diff.new_file or diff.deleted_file:
            continue

        line_matches = re.findall(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff.diff)
        for start_str, count_str in line_matches:
            start = int(start_str)
            count = int(count_str) if count_str else 1
            end = start + max(count - 1, 0)

            blame_results = git_ops.blame_lines(repo_dir, diff.new_path, start, end)
            for blame in blame_results:
                sha = blame.get("sha", "")
                if sha and not sha.startswith("0" * 8):
                    mr_iid = git_ops.find_merge_commit_for_sha(repo_dir, sha)
                    entries.append(
                        BlameEntry(
                            file_path=diff.new_path,
                            line_range=f"{start}-{end}",
                            commit_sha=sha,
                            mr_iid=mr_iid,
                        )
                    )

    return entries


def analyze_scope(
    mr: MRAnalysisInput,
    gitlab_client: GitLabClient | None = None,
    git_ops: GitOps | None = None,
    repo_dir: Path | None = None,
    group_path: str | None = None,
) -> ChangeScope:
    ticket_refs = extract_ticket_refs(mr)
    code_deps = extract_code_dependencies(mr)

    related_mrs: list[RelatedMR] = []
    if gitlab_client and group_path:
        related_mrs = find_related_mrs(ticket_refs, mr, gitlab_client, group_path)

    blame_history: list[BlameEntry] = []
    if git_ops and repo_dir:
        blame_history = run_blame_analysis(mr, git_ops, repo_dir)

    cross_repo = len(related_mrs) > 0

    return ChangeScope(
        ticket_references=ticket_refs,
        related_mrs=related_mrs,
        code_dependencies=code_deps,
        blame_history=blame_history,
        cross_repo_impact=cross_repo,
    )
