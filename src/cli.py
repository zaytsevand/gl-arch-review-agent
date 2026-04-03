from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

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


@click.group()
@click.option("--gitlab-url", envvar="GITLAB_URL", default="https://gitlab.com")
@click.option("--gitlab-token", envvar="GITLAB_TOKEN", required=True)
@click.option("--anthropic-key", envvar="ANTHROPIC_API_KEY", required=True)
@click.option("--arch-repo", required=True, help="Path of architecture-decisions repo")
@click.option("--model", default="claude-sonnet-4-6", help="LLM model for analysis")
@click.option("--dry-run", is_flag=True, help="Analyze without committing or commenting")
@click.option("--verbose", is_flag=True, help="Show classification reasoning")
@click.pass_context
def cli(ctx, gitlab_url, gitlab_token, anthropic_key, arch_repo, model, dry_run, verbose):
    ctx.ensure_object(dict)
    ctx.obj["gitlab_url"] = gitlab_url
    ctx.obj["gitlab_token"] = gitlab_token
    ctx.obj["anthropic_key"] = anthropic_key
    ctx.obj["arch_repo"] = arch_repo
    ctx.obj["model"] = model
    ctx.obj["dry_run"] = dry_run
    ctx.obj["verbose"] = verbose


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
        check_pipeline(gitlab_client, obj["arch_repo"])


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
        except Exception as e:
            click.echo(click.style(f"  FAILED: {mr.project_path}!{mr.mr_iid} — {e}", fg="red"))
            continue

    state_manager.save()

    if not obj["dry_run"]:
        files_to_commit = ["ARCHITECTURE_DECISION_LOG.md", ".agent-state.json"]
        if (arch_repo_dir / "adr").exists():
            files_to_commit.append("adr/")
        git_ops.stage_and_commit(arch_repo_dir, files_to_commit, f"docs: analyze MRs from {repo_path}")
        git_ops.push(arch_repo_dir)
        check_pipeline(gitlab_client, obj["arch_repo"])


@cli.command("review-group")
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
            except Exception as e:
                click.echo(click.style(f"\n  FAILED: {mr.project_path}!{mr.mr_iid} — {e}", fg="red"))
                failed += 1
                continue

    state_manager.save()
    click.echo(f"\nProcessed: {processed}, Skipped: {skipped}, Failed: {failed}")

    if not obj["dry_run"]:
        files_to_commit = ["ARCHITECTURE_DECISION_LOG.md", ".agent-state.json"]
        if (arch_repo_dir / "adr").exists():
            files_to_commit.append("adr/")
        git_ops.stage_and_commit(arch_repo_dir, files_to_commit, f"docs: analyze MRs from group {group_path}")
        git_ops.push(arch_repo_dir)
        check_pipeline(gitlab_client, obj["arch_repo"])


if __name__ == "__main__":
    cli()
