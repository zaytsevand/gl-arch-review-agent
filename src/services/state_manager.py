from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from src.adapters.vcs_types import PullRequest
from src.models.state import MRState, ProcessingState


class StateManager:
    def __init__(self, state_path: Path):
        self.state_path = state_path
        self.state = self._load()

    def _load(self) -> ProcessingState:
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text())
            return ProcessingState.model_validate(data)
        return ProcessingState()

    def save(self) -> None:
        self.state.last_run = datetime.utcnow()
        self.state_path.write_text(
            self.state.model_dump_json(indent=2, exclude_none=True)
        )

    def mr_key(self, project_path: str, mr_iid: int) -> str:
        return f"{project_path}!{mr_iid}"

    def has_changed(self, mr: PullRequest) -> bool:
        key = self.mr_key(mr.repo_path, mr.pr_id)
        prev = self.state.analyzed_mrs.get(key)
        if prev is None:
            return True

        latest_sha = mr.commits[0].sha if mr.commits else ""
        desc_hash = hashlib.sha256(mr.description.encode()).hexdigest()[:16]
        disc_count = len(mr.discussions)

        return (
            prev.last_commit_sha != latest_sha
            or prev.description_hash != desc_hash
            or prev.discussion_count != disc_count
            or prev.pipeline_status != mr.ci_status
        )

    def record_analysis(
        self,
        mr: PullRequest,
        significance: str,
        adl_entry_number: int | None = None,
        adr_file: str | None = None,
    ) -> None:
        key = self.mr_key(mr.repo_path, mr.pr_id)
        latest_sha = mr.commits[0].sha if mr.commits else ""
        desc_hash = hashlib.sha256(mr.description.encode()).hexdigest()[:16]

        self.state.analyzed_mrs[key] = MRState(
            project_path=mr.repo_path,
            mr_iid=mr.pr_id,
            last_commit_sha=latest_sha,
            description_hash=desc_hash,
            discussion_count=len(mr.discussions),
            pipeline_status=mr.ci_status,
            significance=significance,
            adl_entry_number=adl_entry_number,
            adr_file=adr_file,
        )

    def get_mr_state(self, project_path: str, mr_iid: int) -> MRState | None:
        key = self.mr_key(project_path, mr_iid)
        return self.state.analyzed_mrs.get(key)

    def next_adl_number(self) -> int:
        num = self.state.adl_next_number
        self.state.adl_next_number += 1
        return num
