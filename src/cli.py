from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import anthropic
import click
import gitlab.exceptions

from src.models.classification import Significance
from src.services.adl_writer import read_ci_config, write_adl
from src.services.adr_writer import write_adr
from src.services.classifier import classify_mr
from src.services.escalation import evaluate_escalation, format_escalation_comment
from src.services.git_ops import GitOps
from src.services.gitlab_client import GitLabClient
from src.services.mr_commenter import post_feedback
from src.services.pipeline_checker import check_pipeline
from src.services.scope_analyzer import analyze_scope
from src.services.state_manager import StateManager
from src.services.baseline_detector import check_baseline_exists, check_staleness
from src.services.baseline_writer import archive_baseline, write_baseline
from src.services.codebase_scanner import scan_repos

logger = logging.getLogger(__name__)


@click.group()
@click.option("--gitlab-url", envvar="GITLAB_URL", default="https://gitlab.com")
@click.option("--gitlab-token", envvar="GITLAB_TOKEN", required=True)
@click.option("--anthropic-key", envvar="ANTHROPIC_API_KEY", required=True)
@click.option("--arch-repo", required=True, help="Path of architecture-decisions repo")
@click.option("--model", default="claude-sonnet-4-6", help="LLM model for analysis")
@click.option("--dry-run", is_flag=True, help="Analyze without committing or commenting")
@click.option("--verbose", is_flag=True, help="Show classification reasoning")
@click.option("--pipeline-timeout", type=int, default=300, help="Pipeline check timeout in seconds")
@click.pass_context
def cli(ctx, gitlab_url, gitlab_token, anthropic_key, arch_repo, model, dry_run, verbose, pipeline_timeout):
    ctx.ensure_object(dict)
    ctx.obj["gitlab_url"] = gitlab_url
    ctx.obj["gitlab_token"] = gitlab_token
    ctx.obj["anthropic_key"] = anthropic_key
    ctx.obj["arch_repo"] = arch_repo
    ctx.obj["model"] = model
    ctx.obj["dry_run"] = dry_run
    ctx.obj["verbose"] = verbose
    ctx.obj["pipeline_timeout"] = pipeline_timeout


async def process_single_mr(
    project_path: str,
    mr_iid: int,
    ctx_obj: dict,
    gitlab_client: GitLabClient,
    git_ops: GitOps,
    state_manager: StateManager,
    arch_repo_dir: Path,
    group_path: str | None = None,
) -> bool:
    mr = gitlab_client.get_mr(project_path, mr_iid)

    if not state_manager.has_changed(mr):
        if ctx_obj["verbose"]:
            click.echo(f"  Skipping {project_path}!{mr_iid} — no changes since last run")
        return True

    click.echo(f"  Analyzing {project_path}!{mr_iid}: {mr.title}")

    scope = analyze_scope(
        mr, gitlab_client=gitlab_client, group_path=group_path
    )

    if ctx_obj["verbose"] and scope.ticket_references:
        click.echo(f"    Ticket refs: {[t.ticket_id for t in scope.ticket_references]}")
        if scope.related_mrs:
            click.echo(f"    Related MRs: {[f'{r.project_path}!{r.mr_iid}' for r in scope.related_mrs]}")

    review = await classify_mr(mr, ctx_obj["anthropic_key"], ctx_obj["model"])

    review = evaluate_escalation(review, state_manager.state)

    if ctx_obj["verbose"]:
        for p in review.perspectives:
            click.echo(
                f"    [{p.perspective}] {p.classification.significance.value} "
                f"({p.classification.confidence.value}): {p.classification.rationale}"
            )
        if review.consensus:
            click.echo(f"    Consensus: {review.consensus_significance.value}")
        else:
            click.echo(f"    No consensus — escalation: {review.escalation_reason}")

    if review.escalation_triggered and not ctx_obj["dry_run"]:
        comment = format_escalation_comment(review)
        gitlab_client.post_mr_note(project_path, mr_iid, comment)
        click.echo(click.style(f"    ESCALATED: {review.escalation_reason}", fg="yellow"))
        state_manager.record_analysis(mr, "escalated")
        return True

    significance = review.consensus_significance or Significance.NON_SIGNIFICANT

    adr_link = None
    adl_entry_number = None

    if significance in (Significance.MODERATE, Significance.HIGH):
        prev_state = state_manager.get_mr_state(project_path, mr_iid)
        existing_number = prev_state.adl_entry_number if prev_state else None

        service_name = project_path.split("/")[-1]
        adl_path = arch_repo_dir / "ARCHITECTURE_DECISION_LOG.md"

        if significance == Significance.HIGH:
            adr_dir = arch_repo_dir / "adr"
            dead_code_flags = [
                p.classification.rationale
                for p in review.perspectives
                if p.classification.change_type.value == "dead_code"
            ]

            adr, adr_path = await write_adr(
                adr_dir=adr_dir,
                number=state_manager.state.adl_next_number
                if not existing_number
                else existing_number,
                review=review,
                mr_title=mr.title,
                mr_description=mr.description,
                mr_urls=[mr.web_url],
                services=[service_name],
                api_key=ctx_obj["anthropic_key"],
                model=ctx_obj["model"],
                dead_code_flags=dead_code_flags or None,
            )
            adr_link = f"adr/{adr_path.name}"
            click.echo(f"    ADR: {adr_link}")

        entry = write_adl(
            adl_path, review, state_manager, service_name,
            adr_link=adr_link, existing_entry_number=existing_number,
        )
        adl_entry_number = entry.number
        click.echo(
            f"    ADL #{entry.number}: [{entry.confidence}] {entry.summary}"
        )

    state_manager.record_analysis(
        mr, significance.value, adl_entry_number, adr_link
    )

    if not ctx_obj["dry_run"]:
        post_feedback(
            mr, review, gitlab_client,
            adl_entry_number=adl_entry_number, adr_link=adr_link,
        )

    return True


@cli.command("review-mr")
@click.argument("mr_ref")
@click.pass_context
def review_mr(ctx, mr_ref):
    """Analyze a single merge request."""
    parts = mr_ref.replace("!", "/").rsplit("/", 1)
    if len(parts) != 2:
        click.echo("Usage: adr-agent review-mr <project_path>!<mr_iid>", err=True)
        sys.exit(3)

    project_path = parts[0]
    mr_iid = int(parts[1])

    obj = ctx.obj
    gitlab_client = GitLabClient(obj["gitlab_url"], obj["gitlab_token"])
    git_ops = GitOps(obj["gitlab_token"], obj["gitlab_url"])
    arch_repo_dir = git_ops.clone_repo(obj["arch_repo"])
    state_path = arch_repo_dir / ".agent-state.json"
    state_manager = StateManager(state_path)

    group_path = "/".join(project_path.split("/")[:-1]) or None

    success = asyncio.run(
        process_single_mr(
            project_path, mr_iid, obj, gitlab_client, git_ops,
            state_manager, arch_repo_dir, group_path,
        )
    )

    state_manager.save()

    if not obj["dry_run"]:
        files_to_commit = [
            "ARCHITECTURE_DECISION_LOG.md",
            ".agent-state.json",
        ]
        if (arch_repo_dir / "adr").exists():
            files_to_commit.append("adr/")

        git_ops.stage_and_commit(
            arch_repo_dir, files_to_commit,
            f"docs: analyze {project_path}!{mr_iid}",
        )
        git_ops.push(arch_repo_dir)
        check_pipeline(gitlab_client, obj["arch_repo"], timeout_seconds=obj["pipeline_timeout"])


@cli.command("review-repo")
@click.argument("repo_path")
@click.option("--state", "mr_state", default="all", type=click.Choice(["opened", "merged", "all"]))
@click.pass_context
def review_repo(ctx, repo_path, mr_state):
    """Analyze all MRs in a repository."""
    obj = ctx.obj
    gitlab_client = GitLabClient(obj["gitlab_url"], obj["gitlab_token"])
    git_ops = GitOps(obj["gitlab_token"], obj["gitlab_url"])
    arch_repo_dir = git_ops.clone_repo(obj["arch_repo"])
    state_path = arch_repo_dir / ".agent-state.json"
    state_manager = StateManager(state_path)

    group_path = "/".join(repo_path.split("/")[:-1]) or None

    click.echo(f"Fetching MRs from {repo_path} (state={mr_state})...")
    mrs = gitlab_client.list_mrs(repo_path, state=mr_state)
    click.echo(f"Found {len(mrs)} MRs")

    for mr in mrs:
        try:
            asyncio.run(
                process_single_mr(
                    mr.project_path, mr.mr_iid, obj, gitlab_client, git_ops,
                    state_manager, arch_repo_dir, group_path,
                )
            )
        except (anthropic.APIError, gitlab.exceptions.GitlabError, OSError) as e:
            click.echo(click.style(f"  FAILED: {mr.project_path}!{mr.mr_iid} — {e}", fg="red"))
            continue

    state_manager.save()

    if not obj["dry_run"]:
        files_to_commit = ["ARCHITECTURE_DECISION_LOG.md", ".agent-state.json"]
        if (arch_repo_dir / "adr").exists():
            files_to_commit.append("adr/")
        git_ops.stage_and_commit(arch_repo_dir, files_to_commit, f"docs: analyze MRs from {repo_path}")
        git_ops.push(arch_repo_dir)
        check_pipeline(gitlab_client, obj["arch_repo"], timeout_seconds=obj["pipeline_timeout"])
@click.argument("group_path")
@click.option("--state", "mr_state", default="all", type=click.Choice(["opened", "merged", "all"]))
@click.pass_context
def review_group(ctx, group_path, mr_state):
    """Analyze all MRs across all repos in a GitLab group."""
    obj = ctx.obj
    gitlab_client = GitLabClient(obj["gitlab_url"], obj["gitlab_token"])
    git_ops = GitOps(obj["gitlab_token"], obj["gitlab_url"])
    arch_repo_dir = git_ops.clone_repo(obj["arch_repo"])
    state_path = arch_repo_dir / ".agent-state.json"
    state_manager = StateManager(state_path)

    # US2: Auto-detect and generate baseline if missing
    group = gitlab_client.gl.groups.get(group_path)
    repo_paths = [p.path_with_namespace for p in group.projects.list(get_all=True)]
    asyncio.run(ensure_baseline(
        obj, gitlab_client, git_ops, state_manager, arch_repo_dir, repo_paths
    ))

    click.echo(f"Fetching MRs from group {group_path} (state={mr_state})...")
    mrs = gitlab_client.list_group_mrs(group_path, state=mr_state)
    click.echo(f"Found {len(mrs)} MRs across group")

    processed = 0
    skipped = 0
    failed = 0

    with click.progressbar(mrs, label="Processing MRs") as bar:
        for mr in bar:
            try:
                asyncio.run(
                    process_single_mr(
                        mr.project_path, mr.mr_iid, obj, gitlab_client, git_ops,
                        state_manager, arch_repo_dir, group_path,
                    )
                )
                processed += 1
            except (anthropic.APIError, gitlab.exceptions.GitlabError, OSError) as e:
                click.echo(click.style(f"\n  FAILED: {mr.project_path}!{mr.mr_iid} — {e}", fg="red"))
                failed += 1
                continue

    state_manager.save()
    click.echo(f"\nProcessed: {processed}, Skipped: {skipped}, Failed: {failed}")

    # US3: Check baseline staleness after batch processing
    if check_staleness(state_manager.state):
        click.echo(click.style(
            "\nBaseline may be stale — significant architectural changes detected since last generation.",
            fg="yellow",
        ))
        click.echo("Run `adr-agent snapshot` to refresh the baseline.")

    if not obj["dry_run"]:
        files_to_commit = ["ARCHITECTURE_DECISION_LOG.md", ".agent-state.json"]
        if (arch_repo_dir / "adr").exists():
            files_to_commit.append("adr/")
        if (arch_repo_dir / "ARCHITECTURE_BASELINE.md").exists():
            files_to_commit.append("ARCHITECTURE_BASELINE.md")
        git_ops.stage_and_commit(arch_repo_dir, files_to_commit, f"docs: analyze MRs from group {group_path}")
        git_ops.push(arch_repo_dir)
        check_pipeline(gitlab_client, obj["arch_repo"], timeout_seconds=obj["pipeline_timeout"])


async def ensure_baseline(
    obj: dict,
    gitlab_client: GitLabClient,
    git_ops: GitOps,
    state_manager: StateManager,
    arch_repo_dir: Path,
    repo_paths: list[str],
) -> None:
    """Auto-generate baseline if missing (US2 integration)."""
    status = check_baseline_exists(arch_repo_dir)
    if status == "valid":
        if obj["verbose"]:
            click.echo("  Baseline exists and is valid — skipping generation")
        return

    click.echo(click.style(
        f"  Baseline {status} — auto-generating before MR analysis...", fg="yellow"
    ))
    baseline = scan_repos(repo_paths, git_ops)
    await write_baseline(
        baseline, arch_repo_dir, obj["anthropic_key"], state_manager.state, obj["model"]
    )
    from datetime import datetime, timezone
    state_manager.state.baseline_generated_at = datetime.now(timezone.utc)
    state_manager.state.baseline_version += 1
    state_manager.state.baseline_repos_scanned = repo_paths
    click.echo(click.style("  Baseline generated successfully", fg="green"))


@cli.command("snapshot")
@click.argument("repo_paths", nargs=-1, required=True)
@click.pass_context
def snapshot(ctx, repo_paths):
    """Generate an Architecture Baseline Document from codebase scan."""
    obj = ctx.obj
    gitlab_client = GitLabClient(obj["gitlab_url"], obj["gitlab_token"])
    git_ops = GitOps(obj["gitlab_token"], obj["gitlab_url"])
    arch_repo_dir = git_ops.clone_repo(obj["arch_repo"])
    state_path = arch_repo_dir / ".agent-state.json"
    state_manager = StateManager(state_path)

    repo_list = list(repo_paths)
    click.echo(f"Scanning {len(repo_list)} repositories...")

    baseline = scan_repos(repo_list, git_ops)
    click.echo(f"Found {len(baseline.services)} services, {len(baseline.communication_links)} communication links")

    baseline_path = asyncio.run(
        write_baseline(
            baseline, arch_repo_dir, obj["anthropic_key"], state_manager.state, obj["model"]
        )
    )

    from datetime import datetime, timezone
    state_manager.state.baseline_generated_at = datetime.now(timezone.utc)
    state_manager.state.baseline_version += 1
    state_manager.state.baseline_repos_scanned = repo_list
    state_manager.save()

    click.echo(f"Baseline written to {baseline_path.name}")

    if baseline.flagged_unknowns:
        pending = [u for u in baseline.flagged_unknowns if u.status == "pending_review"]
        if pending:
            click.echo(click.style(
                f"  {len(pending)} items flagged for human review", fg="yellow"
            ))

    if not obj["dry_run"]:
        files = ["ARCHITECTURE_BASELINE.md", ".agent-state.json"]
        git_ops.stage_and_commit(
            arch_repo_dir, files, "docs: generate architecture baseline"
        )
        git_ops.push(arch_repo_dir)
        check_pipeline(gitlab_client, obj["arch_repo"], timeout_seconds=obj["pipeline_timeout"])

    click.echo(click.style("Baseline snapshot complete", fg="green"))


if __name__ == "__main__":
    cli()
