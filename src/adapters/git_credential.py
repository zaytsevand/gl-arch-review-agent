"""Platform-aware credential helpers for Git clone URLs."""

from __future__ import annotations


def format_clone_url(provider: str, base_url: str, token: str, repo_path: str) -> str:
    """Build an authenticated HTTPS clone URL.

    Parameters
    ----------
    provider:
        ``"gitlab"`` or ``"github"``.
    base_url:
        Base URL of the VCS instance (e.g. ``https://gitlab.com``).
    token:
        Personal access token / app token.
    repo_path:
        ``owner/repo`` style path.

    Returns
    -------
    str
        Authenticated clone URL.
    """
    host = base_url.replace("https://", "").replace("http://", "").rstrip("/")

    if provider == "github":
        return f"https://x-access-token:{token}@{host}/{repo_path}.git"

    # gitlab (default)
    return f"https://oauth2:{token}@{host}/{repo_path}.git"
