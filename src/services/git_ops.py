from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class GitOps:
    def __init__(self, token: str, gitlab_url: str = "https://gitlab.com"):
        self.token = token
        self.gitlab_url = gitlab_url
        self._temp_dirs: list[Path] = []
        self._askpass_files: list[Path] = []

    def _git_env(self) -> dict[str, str]:
        """Return environment with GIT_ASKPASS for credential injection.

        This avoids embedding the token in URLs, which would leak it
        in CalledProcessError messages and process listings.
        """
        askpass_script = (
            "#!/bin/sh\n"
            f'echo "{self.token}"'
        )
        fd, askpass_path = tempfile.mkstemp(prefix="adr-askpass-", suffix=".sh")
        with os.fdopen(fd, "w") as f:
            f.write(askpass_script)
        os.chmod(askpass_path, 0o700)
        self._askpass_files.append(Path(askpass_path))
        env = os.environ.copy()
        env["GIT_ASKPASS"] = askpass_path
        env["GIT_TERMINAL_PROMPT"] = "0"
        return env

    def _repo_url(self, project_path: str) -> str:
        """Build clone URL with username only — password provided via GIT_ASKPASS."""
        host = self.gitlab_url.replace("https://", "").replace("http://", "")
        return f"https://oauth2@{host}/{project_path}.git"

    def clone_repo(self, project_path: str, target_dir: str | None = None) -> Path:
        if target_dir is None:
            target_dir = tempfile.mkdtemp(prefix="adr-agent-")
        url = self._repo_url(project_path)
        try:
            subprocess.run(
                ["git", "clone", "--quiet", url, target_dir],
                check=True,
                capture_output=True,
                env=self._git_env(),
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to clone {project_path} (exit code {exc.returncode})"
            ) from None
        result = Path(target_dir)
        self._temp_dirs.append(result)
        return result

    def get_default_branch(self, repo_dir: Path) -> str:
        """Detect the default branch of a cloned repo."""
        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip().replace("refs/remotes/origin/", "")
        except subprocess.CalledProcessError:
            return "main"

    def blame_lines(
        self, repo_dir: Path, file_path: str, start_line: int, end_line: int
    ) -> list[dict]:
        try:
            result = subprocess.run(
                [
                    "git",
                    "blame",
                    "-L",
                    f"{start_line},{end_line}",
                    "--porcelain",
                    file_path,
                ],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            return []

        entries = []
        current_sha = None
        for line in result.stdout.splitlines():
            sha_match = re.match(r"^([0-9a-f]{40})\s", line)
            if sha_match:
                current_sha = sha_match.group(1)
                if current_sha not in [e.get("sha") for e in entries]:
                    entries.append({"sha": current_sha})

        return entries

    def find_merge_commit_for_sha(self, repo_dir: Path, sha: str) -> int | None:
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--merges",
                    "--grep=See merge request",
                    "--ancestry-path",
                    f"{sha}..HEAD",
                    "--oneline",
                    "-1",
                ],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            return None

        match = re.search(r"See merge request .+!(\d+)", result.stdout)
        if match:
            return int(match.group(1))
        return None

    def stage_and_commit(
        self, repo_dir: Path, files: list[str], message: str
    ) -> str:
        for f in files:
            subprocess.run(
                ["git", "add", f], cwd=repo_dir, check=True, capture_output=True
            )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return sha_result.stdout.strip()

    def push(self, repo_dir: Path, branch: str | None = None, max_retries: int = 3) -> None:
        if branch is None:
            branch = self.get_default_branch(repo_dir)
        env = self._git_env()
        for attempt in range(1, max_retries + 1):
            result = subprocess.run(
                ["git", "push", "origin", branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode == 0:
                return

            if attempt < max_retries and (
                "rejected" in result.stderr or "fetch first" in result.stderr
            ):
                try:
                    subprocess.run(
                        ["git", "pull", "--rebase", "origin", branch],
                        cwd=repo_dir,
                        check=True,
                        capture_output=True,
                        env=env,
                    )
                except subprocess.CalledProcessError:
                    logger.warning(
                        "Rebase failed on attempt %d/%d for %s",
                        attempt, max_retries, repo_dir,
                    )
                    subprocess.run(
                        ["git", "rebase", "--abort"],
                        cwd=repo_dir,
                        capture_output=True,
                    )
                continue

            raise RuntimeError(
                f"Failed to push to {branch} after {max_retries} attempts: {result.stderr}"
            )

    def cleanup(self) -> None:
        """Remove all temporary directories and askpass scripts created by this instance."""
        for d in self._temp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        self._temp_dirs.clear()
        for f in self._askpass_files:
            f.unlink(missing_ok=True)
        self._askpass_files.clear()
