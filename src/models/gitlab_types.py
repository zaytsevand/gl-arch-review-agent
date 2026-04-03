from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Note(BaseModel):
    author: str
    body: str
    created_at: datetime
    system: bool = False


class Discussion(BaseModel):
    id: str
    notes: list[Note]
    resolved: bool = False
    file_path: str | None = None
    line_number: int | None = None


class FileDiff(BaseModel):
    old_path: str
    new_path: str
    diff: str
    new_file: bool = False
    deleted_file: bool = False
    renamed_file: bool = False


class CommitInfo(BaseModel):
    sha: str
    title: str
    message: str = ""
    authored_date: datetime | None = None


class MRAnalysisInput(BaseModel):
    project_id: int
    project_path: str
    mr_iid: int
    title: str
    description: str = ""
    source_branch: str
    target_branch: str = "main"
    state: str = "opened"
    author: str = ""
    diffs: list[FileDiff] = []
    discussions: list[Discussion] = []
    pipeline_status: str = ""
    commits: list[CommitInfo] = []
    web_url: str = ""
