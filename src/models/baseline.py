from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TechStack(BaseModel):
    language: str = ""
    framework: str = ""
    build_tool: str = ""
    key_dependencies: list[str] = Field(default_factory=list)


class APIEndpoint(BaseModel):
    method: str = "GET"
    path: str = ""
    controller_class: str = ""
    request_dto: str | None = None
    response_dto: str | None = None


class ConsumedAPI(BaseModel):
    target_service: str = ""
    url_pattern: str = ""
    client_class: str = ""
    protocol: str = "REST"


class DataStore(BaseModel):
    name: str = ""
    technology: str = ""
    entities: list[str] = Field(default_factory=list)
    config_source: str = ""


class CIConfig(BaseModel):
    stages: list[str] = Field(default_factory=list)
    image: str = ""
    key_commands: list[str] = Field(default_factory=list)


class ServiceInventoryEntry(BaseModel):
    name: str
    repo_path: str = ""
    responsibility: str = ""
    tech_stack: TechStack = Field(default_factory=TechStack)
    exposed_apis: list[APIEndpoint] = Field(default_factory=list)
    consumed_apis: list[ConsumedAPI] = Field(default_factory=list)
    data_stores: list[DataStore] = Field(default_factory=list)
    ci_config: CIConfig | None = None


class CommunicationLink(BaseModel):
    source_service: str
    target_service: str
    protocol: str = "REST"
    contract: str = ""
    direction: str = "sync"


class ExternalRef(BaseModel):
    url: str
    source_file: str = ""
    context: str = ""
    fetched_content: str | None = None


class FlaggedUnknown(BaseModel):
    description: str
    location: str = ""
    agent_assessments: list[str] = Field(default_factory=list)
    status: str = "pending_review"
    resolution: str | None = None


class BaselineDocument(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    repos_scanned: list[str] = Field(default_factory=list)
    branches_scanned: list[str] = Field(default_factory=list)
    services: list[ServiceInventoryEntry] = Field(default_factory=list)
    communication_links: list[CommunicationLink] = Field(default_factory=list)
    external_references: list[ExternalRef] = Field(default_factory=list)
    flagged_unknowns: list[FlaggedUnknown] = Field(default_factory=list)
