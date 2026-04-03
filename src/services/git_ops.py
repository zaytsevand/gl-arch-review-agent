from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path


class GitOps:
    def __init__(self, token: str, gitlab_url: str = "https://gitlab.com"):
        self.token = token
        self.gitlab_url = gitlab_url

    def clone_repo(self, project_path: str, target_dir: str | None = None) -> Path:
        if target_dir is None:
            target_dir = tempfile.mkdtemp(prefix="adr-agent-")
        url = f"https://oauth2:{self.token}@{self.gitlab_url.replace('https://', '')}/{project_path}.git"
        subprocess.run(
            ["git", "clone", "--quiet", url, target_dir],
            check=True,
            capture_output=True,
        )
        return Path(target_dir)

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
        result = subprocess.run(
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

    def push(self, repo_dir: Path, branch: str = "main", max_retries: int = 3) -> None:
        for attempt in range(1, max_retries + 1):
            result = subprocess.run(
                ["git", "push", "origin", branch],
                cwd=repo_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return

            if attempt < max_retries and (
                "rejected" in result.stderr or "fetch first" in result.stderr
            ):
                subprocess.run(
                    ["git", "pull", "--rebase", "origin", branch],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )
                continue

            raise subprocess.CalledProcessError(
                result.returncode,
                result.args,
                output=result.stdout,
                stderr=result.stderr,
            )
