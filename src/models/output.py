from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class Alternative(BaseModel):
    name: str
    reason_rejected: str


class ADLEntry(BaseModel):
    number: int
    date: date
    service: str
    change_type: str
    confidence: str  # High, Medium, Borderline
    summary: str
    rationale: str
    adr_link: str | None = None  # relative path to ADR file, or None


class ADRDocument(BaseModel):
    number: int
    title: str
    date: date
    status: str = "Proposed"
    confidence: str
    services: list[str] = []
    source_mr_urls: list[str] = []
    context: str = ""
    decision: str = ""
    alternatives: list[Alternative] = []
    consequences: list[str] = []
