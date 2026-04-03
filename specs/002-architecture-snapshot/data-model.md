# Data Model: Architecture Baseline Snapshot

**Feature**: 002-architecture-snapshot | **Date**: 2026-04-03

## New Entities (extends Feature 001 data model)

### ServiceInventoryEntry

| Field | Type | Description |
|-------|------|-------------|
| name | str | Service name (e.g., `order-service`) |
| repo_path | str | GitLab project path |
| responsibility | str | One-line description of what the service does |
| tech_stack | TechStack | Language, framework, build tool |
| exposed_apis | list[APIEndpoint] | REST endpoints this service exposes |
| consumed_apis | list[ConsumedAPI] | External APIs this service calls |
| data_stores | list[DataStore] | Databases/caches used |
| ci_config | CIConfig | null | CI/CD pipeline summary |

### TechStack

| Field | Type | Description |
|-------|------|-------------|
| language | str | e.g., `Java 21` |
| framework | str | e.g., `Spring Boot 3.2.3` |
| build_tool | str | e.g., `Gradle 8.5` |
| key_dependencies | list[str] | Notable deps (e.g., `spring-boot-starter-web`, `h2`) |

### APIEndpoint

| Field | Type | Description |
|-------|------|-------------|
| method | str | HTTP method (GET, POST, etc.) |
| path | str | URL path (e.g., `/api/orders`) |
| controller_class | str | Class name handling this endpoint |
| request_dto | str | null | Request body DTO name |
| response_dto | str | null | Response body DTO name |

### ConsumedAPI

| Field | Type | Description |
|-------|------|-------------|
| target_service | str | Service being called |
| url_pattern | str | URL or config property reference |
| client_class | str | Class making the call |
| protocol | str | `REST`, `Feign`, `WebSocket`, `gRPC` |

### DataStore

| Field | Type | Description |
|-------|------|-------------|
| name | str | Database/cache name |
| technology | str | e.g., `H2`, `PostgreSQL`, `Redis` |
| entities | list[str] | JPA entity names managed |
| config_source | str | Config file where connection is defined |

### CIConfig

| Field | Type | Description |
|-------|------|-------------|
| stages | list[str] | Pipeline stages (e.g., `build`, `test`) |
| image | str | Docker image used |
| key_commands | list[str] | Main commands per stage |

### CommunicationLink

| Field | Type | Description |
|-------|------|-------------|
| source_service | str | Calling service |
| target_service | str | Called service |
| protocol | str | REST, WebSocket, Queue, etc. |
| contract | str | Shared DTO or schema name |
| direction | str | `sync`, `async`, `bidirectional` |

### BaselineDocument

Top-level model for the complete baseline.

| Field | Type | Description |
|-------|------|-------------|
| generated_at | datetime | Generation timestamp |
| repos_scanned | list[str] | Repository paths scanned |
| branches_scanned | list[str] | Branch names scanned (usually `main`) |
| services | list[ServiceInventoryEntry] | All discovered services |
| communication_links | list[CommunicationLink] | Inter-service connections |
| external_references | list[ExternalRef] | Confluence/Jira links found |
| flagged_unknowns | list[FlaggedUnknown] | Items needing human review |

### ExternalRef

| Field | Type | Description |
|-------|------|-------------|
| url | str | The reference URL |
| source_file | str | Where it was found |
| context | str | Surrounding text/purpose |
| fetched_content | str | null | Content if successfully retrieved |

### FlaggedUnknown

| Field | Type | Description |
|-------|------|-------------|
| description | str | What was found |
| location | str | File and line where found |
| agent_assessments | list[str] | Multi-agent review results |
| status | str | `pending_review`, `resolved` |
| resolution | str | null | Human's decision |
