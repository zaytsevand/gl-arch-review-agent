from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class MRState(BaseModel):
    project_path: str
    mr_iid: int
    last_commit_sha: str = ""
    description_hash: str = ""
    discussion_count: int = 0
    pipeline_status: str = ""
    significance: str = ""
    adl_entry_number: int | None = None
    adr_file: str | None = None


class EscalationPrecedent(BaseModel):
    pattern_hash: str
    human_decision: str
    resolved_date: date
    context_summary: str = ""


class ProcessingState(BaseModel):
    version: str = "1.0"
    last_run: datetime | None = None
    analyzed_mrs: dict[str, MRState] = Field(default_factory=dict)
    escalation_precedents: list[EscalationPrecedent] = Field(default_factory=list)
    adl_next_number: int = 1
    baseline_generated_at: datetime | None = None
    baseline_version: int = 0
    baseline_repos_scanned: list[str] = Field(default_factory=list)
