"""Tests for git_ops — token security, branch detection, cleanup."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.git_ops import GitOps


@pytest.fixture
def git_ops():
    return GitOps(token="secret-token-12345", gitlab_url="https://gitlab.example.com")


class TestTokenSecurity:
    """Verify the token never leaks into URLs, args, or error messages."""

    def test_repo_url_excludes_token(self, git_ops):
        url = git_ops._repo_url("group/repo")
        assert "secret-token-12345" not in url
        assert "oauth2@" in url

    def test_git_env_uses_askpass(self, git_ops):
        env = git_ops._git_env()
        assert "GIT_ASKPASS" in env
        askpass_path = env["GIT_ASKPASS"]
        assert os.path.isfile(askpass_path)
        content = Path(askpass_path).read_text()
        assert "secret-token-12345" in content
        # Askpass files should be tracked for cleanup
        assert len(git_ops._askpass_files) == 1
        git_ops.cleanup()
        assert not os.path.exists(askpass_path)

    @patch("src.services.git_ops.subprocess.run")
    def test_clone_error_hides_token(self, mock_run, git_ops):
        mock_run.side_effect = subprocess.CalledProcessError(
            128, ["git", "clone"], stderr="fatal: authentication failed"
        )
        with pytest.raises(RuntimeError, match="Failed to clone group/repo"):
            git_ops.clone_repo("group/repo", "/tmp/test-clone")
        # The RuntimeError message must NOT contain the token
        try:
            git_ops.clone_repo("group/repo", "/tmp/test-clone2")
        except RuntimeError as e:
            assert "secret-token-12345" not in str(e)


class TestDefaultBranch:
    """Test default branch detection."""

    @patch("src.services.git_ops.subprocess.run")
    def test_detect_main(self, mock_run, git_ops):
        mock_run.return_value = MagicMock(
            stdout="refs/remotes/origin/main\n", returncode=0
        )
        assert git_ops.get_default_branch(Path("/fake")) == "main"

    @patch("src.services.git_ops.subprocess.run")
    def test_detect_master(self, mock_run, git_ops):
        mock_run.return_value = MagicMock(
            stdout="refs/remotes/origin/master\n", returncode=0
        )
        assert git_ops.get_default_branch(Path("/fake")) == "master"

    @patch("src.services.git_ops.subprocess.run")
    def test_fallback_on_error(self, mock_run, git_ops):
        mock_run.side_effect = subprocess.CalledProcessError(1, [])
        assert git_ops.get_default_branch(Path("/fake")) == "main"


class TestTempCleanup:
    """Test temp directory tracking and cleanup."""

    def test_cleanup_removes_tracked_dirs(self, git_ops, tmp_path):
        d1 = tmp_path / "dir1"
        d1.mkdir()
        d2 = tmp_path / "dir2"
        d2.mkdir()
        git_ops._temp_dirs = [d1, d2]

        git_ops.cleanup()

        assert not d1.exists()
        assert not d2.exists()
        assert git_ops._temp_dirs == []

    def test_cleanup_ignores_missing_dirs(self, git_ops, tmp_path):
        missing = tmp_path / "nonexistent"
        git_ops._temp_dirs = [missing]
        git_ops.cleanup()  # should not raise
        assert git_ops._temp_dirs == []


class TestPushRebaseRecovery:
    """Test push retry with rebase conflict recovery."""

    @patch("src.services.git_ops.subprocess.run")
    def test_push_rebase_abort_on_conflict(self, mock_run, git_ops):
        """If rebase fails, it should abort and retry."""
        # First push: rejected
        push_fail = MagicMock(returncode=1, stderr="rejected", stdout="")
        # Rebase: conflict
        rebase_fail = subprocess.CalledProcessError(1, ["git", "pull", "--rebase"])
        # Rebase abort: ok
        abort_ok = MagicMock(returncode=0)
        # Second push: rejected
        push_fail2 = MagicMock(returncode=1, stderr="rejected", stdout="")
        # Rebase: ok
        rebase_ok = MagicMock(returncode=0)
        # Third push: success
        push_ok = MagicMock(returncode=0)

        mock_run.side_effect = [
            push_fail, rebase_fail, abort_ok,
            push_fail2, rebase_ok,
            push_ok,
        ]

        git_ops.push(Path("/fake"), branch="main")  # should not raise
