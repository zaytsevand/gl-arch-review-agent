"""Backward-compatibility shim — re-exports ``GitLabAdapter`` as ``GitLabClient``.

New code should use ``src.adapters.gitlab_adapter.GitLabAdapter`` or
the generic ``VCSClient`` interface instead.
"""

from __future__ import annotations

from src.adapters.gitlab_adapter import GitLabAdapter as GitLabClient

__all__ = ["GitLabClient"]

