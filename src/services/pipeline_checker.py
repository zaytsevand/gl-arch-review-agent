from __future__ import annotations

import time

import click

from src.services.gitlab_client import GitLabClient


def check_pipeline(
    gitlab_client: GitLabClient,
    project_path: str,
    ref: str = "main",
    timeout_seconds: int | None = None,
    poll_interval: int = 10,
) -> str:
    if timeout_seconds is None:
        timeout_seconds = 300
    elapsed = 0
    while elapsed < timeout_seconds:
        status = gitlab_client.get_pipeline_status(project_path, ref)

        if status in ("success", "failed", "canceled", "skipped"):
            if status != "success":
                click.echo(
                    click.style(
                        f"Pipeline {status} for {project_path} on {ref}",
                        fg="red",
                    )
                )
            else:
                click.echo(
                    click.style(
                        f"Pipeline passed for {project_path} on {ref}",
                        fg="green",
                    )
                )
            return status

        if status == "unknown":
            click.echo(f"No pipeline found for {project_path} on {ref}")
            return "unknown"

        time.sleep(poll_interval)
        elapsed += poll_interval

    click.echo(f"Pipeline timed out after {timeout_seconds}s for {project_path}")
    return "timeout"
