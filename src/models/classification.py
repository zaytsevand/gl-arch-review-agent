from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class Significance(str, Enum):
    NON_SIGNIFICANT = "non_significant"
    MODERATE = "moderate"
    HIGH = "high"


class ChangeType(str, Enum):
    API_CHANGE = "api_change"
    NEW_DEPENDENCY = "new_dependency"
    SCHEMA_CHANGE = "schema_change"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    CONFIG_CHANGE = "config_change"
    DEAD_CODE = "dead_code"
    CONTRACT_CHANGE = "contract_change"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    BORDERLINE = "borderline"


class SignificanceClassification(BaseModel):
    significance: Significance
    change_type: ChangeType
    confidence: Confidence
    summary: str
    rationale: str
    affected_services: list[str] = []
    areas_of_impact: list[str] = []
    relevant_files: list[str] = []


class TicketRef(BaseModel):
    ticket_id: str
    source: str  # mr_title, mr_description, commit_message, code_comment
    project_path: str


class RelatedMR(BaseModel):
    project_path: str
    mr_iid: int
    title: str
    shared_ticket: str


class BlameEntry(BaseModel):
    file_path: str
    line_range: str
    commit_sha: str
    mr_iid: int | None = None
    age_days: int = 0


class ChangeScope(BaseModel):
    ticket_references: list[TicketRef] = []
    related_mrs: list[RelatedMR] = []
    documented_dependencies: list[str] = []
    code_dependencies: list[str] = []
    blame_history: list[BlameEntry] = []
    cross_repo_impact: bool = False


class PerspectiveResult(BaseModel):
    perspective: str  # api_contract, dependency_coupling, risk_security
    classification: SignificanceClassification


class MultiAgentReview(BaseModel):
    perspectives: list[PerspectiveResult] = []
    consensus: bool = False
    consensus_significance: Significance | None = None
    consensus_confidence: Confidence = Confidence.MEDIUM
    escalation_triggered: bool = False
    escalation_reason: str | None = None
