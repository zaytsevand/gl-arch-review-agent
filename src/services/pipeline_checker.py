from __future__ import annotations

import time

import click

from src.adapters.vcs_client import VCSClient
from src.adapters.vcs_types import CIStatus

_TERMINAL_STATUSES = {CIStatus.SUCCESS, CIStatus.FAILURE, CIStatus.CANCELLED}


def check_pipeline(
    vcs_client: VCSClient,
    project_path: str,
    ref: str = "main",
    timeout_seconds: int = 300,
    poll_interval: int = 10,
) -> str:
    elapsed = 0
    while elapsed < timeout_seconds:
        status = vcs_client.get_ci_status(project_path, ref)

        if status in _TERMINAL_STATUSES:
            if status != CIStatus.SUCCESS:
                click.echo(
                    click.style(
                        f"Pipeline {status.value} for {project_path} on {ref}",
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
            return status.value

        if status == CIStatus.UNKNOWN:
            click.echo(f"No pipeline found for {project_path} on {ref}")
            return "unknown"

        time.sleep(poll_interval)
        elapsed += poll_interval

    click.echo(f"Pipeline timed out after {timeout_seconds}s for {project_path}")
    return "timeout"
