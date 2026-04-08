"""Factory for creating the correct VCS adapter based on provider name."""

from __future__ import annotations

from src.adapters.vcs_client import VCSClient


def create_vcs_client(provider: str, url: str, token: str) -> VCSClient:
    """Instantiate and authenticate a VCS client.

    Parameters
    ----------
    provider:
        ``"gitlab"`` or ``"github"``.
    url:
        Base URL of the VCS instance.
    token:
        Personal/app access token.

    Returns
    -------
    VCSClient
        Authenticated adapter instance.

    Raises
    ------
    ValueError
        If *provider* is not supported.
    RuntimeError
        If the required SDK package is not installed.
    """
    if provider == "gitlab":
        try:
            from src.adapters.gitlab_adapter import GitLabAdapter
        except ImportError as exc:
            raise RuntimeError(
                "python-gitlab is not installed. "
                "Install it with: pip install 'adr-agent[gitlab]'"
            ) from exc
        client = GitLabAdapter(url, token)
        client.authenticate()
        return client

    if provider == "github":
        try:
            from src.adapters.github_adapter import GitHubAdapter
        except ImportError as exc:
            raise RuntimeError(
                "PyGithub is not installed. "
                "Install it with: pip install 'adr-agent[github]'"
            ) from exc
        client = GitHubAdapter(url, token)
        client.authenticate()
        return client

    raise ValueError(
        f"Unsupported VCS provider: {provider!r}. Choose 'gitlab' or 'github'."
    )
