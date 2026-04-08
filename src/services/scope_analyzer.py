from __future__ import annotations

import re
from pathlib import Path

from src.models.classification import BlameEntry, ChangeScope, RelatedMR, TicketRef
from src.adapters.vcs_types import PullRequest
from src.adapters.vcs_client import VCSClient
from src.services.git_ops import GitOps

TICKET_PATTERN = re.compile(r"[A-Z]{2,10}-\d+")


def extract_ticket_refs(mr: PullRequest) -> list[TicketRef]:
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
                    project_path=mr.repo_path,
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
    current_mr: PullRequest,
    vcs_client: VCSClient,
    group_path: str,
) -> list[RelatedMR]:
    related: list[RelatedMR] = []
    ticket_ids = {ref.ticket_id for ref in ticket_refs}

    if not ticket_ids:
        return related

    repo_paths = vcs_client.list_org_repos(group_path)

    for repo_path in repo_paths:
        if repo_path == current_mr.repo_path:
            continue

        try:
            prs = vcs_client.list_pull_requests(repo_path, state="all")
            for pr in prs:
                for ticket_id in ticket_ids:
                    if ticket_id in (pr.title or "") or ticket_id in (
                        pr.description or ""
                    ):
                        related.append(
                            RelatedMR(
                                project_path=repo_path,
                                mr_iid=pr.pr_id,
                                title=pr.title,
                                shared_ticket=ticket_id,
                            )
                        )
                        break
        except Exception:
            continue

    return related


def extract_code_dependencies(mr: PullRequest) -> list[str]:
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
    mr: PullRequest, git_ops: GitOps, repo_dir: Path
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
    mr: PullRequest,
    vcs_client: VCSClient | None = None,
    git_ops: GitOps | None = None,
    repo_dir: Path | None = None,
    group_path: str | None = None,
) -> ChangeScope:
    ticket_refs = extract_ticket_refs(mr)
    code_deps = extract_code_dependencies(mr)

    related_mrs: list[RelatedMR] = []
    if vcs_client and group_path:
        related_mrs = find_related_mrs(ticket_refs, mr, vcs_client, group_path)

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
