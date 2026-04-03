# Research: ADR Review Agent

**Feature**: 001-adr-review-agent | **Date**: 2026-04-03

## Tech Stack Decisions

### Language: Python 3.11+

**Decision**: Python
**Rationale**: Best LLM ecosystem (Anthropic SDK is Python-first), fastest prototype iteration, simple `pip install` for 30-minute setup goal. Go/TypeScript offer no advantage for an API-call-heavy CLI prototype.
**Alternatives**: TypeScript (weaker GitLab/LLM libraries), Go (overkill for prototype, slower iteration)

### LLM SDK: Anthropic Python SDK (direct)

**Decision**: `anthropic` package, direct API calls
**Rationale**: Multi-agent review is just parallel LLM calls with different system prompts — `asyncio.gather()` over prompt templates. No framework needed. Use Anthropic tool_use for structured JSON output (classification, ADR fields). Eliminates fragile regex parsing.
**Alternatives**: LangChain (unnecessary abstraction, harder debugging), CrewAI/AutoGen (solve agent conversation, not fan-out/fan-in), LiteLLM (viable for multi-provider, but premature for prototype)

### GitLab Client: python-gitlab

**Decision**: `python-gitlab` library
**Rationale**: Mature, full API coverage — MRs, diffs, discussions, pipelines, commits, repository files. Handles pagination and auth natively.
**Alternatives**: Raw HTTP (more work, no benefit), glab CLI (not programmatic)

### Git Operations: subprocess

**Decision**: Shell out to `git` directly
**Rationale**: Need only 4-5 commands (clone, blame, add, commit, push). GitPython adds dependency weight without value for this scope.
**Alternatives**: GitPython (unnecessary abstraction)

### CLI Framework: click

**Decision**: `click`
**Rationale**: Subcommands (`review-mr`, `review-repo`, `review-group`, `snapshot`), env-var fallback for tokens, progress bars for batch processing.
**Alternatives**: argparse (verbose), typer (magic inference)

### Testing: pytest + respx

**Decision**: `pytest` with `respx` for HTTP mocking
**Rationale**: Standard Python testing. Mock GitLab API responses. For LLM output, snapshot expected JSON structures.
**Alternatives**: unittest (verbose), responses (similar but respx is async-compatible)

### Data Modeling: Pydantic

**Decision**: `pydantic` for all data models
**Rationale**: Single source of truth — used as (1) JSON schema for Anthropic tool_use, (2) state persistence serialization, (3) input to Jinja2 markdown templates. Validation included.
**Alternatives**: dataclasses (no validation), attrs (less ecosystem integration)

### Markdown Rendering: Jinja2

**Decision**: `jinja2` templates for ADL/ADR/baseline markdown
**Rationale**: Separates content from presentation. Templates can be validated against markdownlint rules. Cleaner than string concatenation.
**Alternatives**: String formatting (fragile), f-strings (unmaintainable for multi-section docs)

### Agent Framework: None (DIY)

**Decision**: No framework — linear pipeline with parallel fan-out
**Rationale**: Data flow is: GitLab API → MR data → fan-out to N analysis prompts → fan-in results → render markdown → git commit. This is `asyncio.gather()`, not a graph. Frameworks add dependencies, indirection, and debugging pain for zero benefit.
**Alternatives**: LangGraph (solves cyclic graphs, not applicable), CrewAI (solves agent delegation, not applicable)

## ADR/ADL Format Decisions

### ADR File Format: Nygard + Alternatives + Confidence

**Decision**: Michael Nygard's original format extended with: Confidence, Services, Source (MR link), Alternatives Considered
**Rationale**: Minimal, proven, widely recognized. LLMs produce better output with fewer sections. "Alternatives" is critical for reviewability. "Confidence" enables human triage.
**Alternatives**: MADR v3 (too verbose for machine-generated), Y-Statements (too terse for standalone files)

### ADL Table Format: Extended existing columns

**Decision**: Extend the sample repo's existing table with Confidence and Rationale columns:
```
| # | Date | Service | Change Type | Confidence | Summary | Rationale | ADR |
```
**Rationale**: Respects existing format (FR-004). Confidence enables triage. Rationale explains WHY, not WHAT. Append-only, newest entry above the comment marker.
**Alternatives**: Replace with YAML (less readable in GitLab), free-form sections (breaks scanability)

### Change Type Taxonomy

**Decision**: Fixed set of change types for consistent classification:
- `API Change` — new/modified REST endpoints, versioning
- `New Dependency` — new inter-service call, Feign client, queue consumer
- `Schema Change` — entity/migration changes visible to other services
- `Infrastructure` — new service, database, queue, WebSocket
- `Security` — auth/authz, CORS, data protection changes
- `Config Change` — deployment, ports, feature flags affecting behavior
- `Dead Code` — incomplete integration, abandoned patterns
- `Contract Change` — shared DTO modifications across services

## LLM Classification Approach

### Two-pass analysis

**Decision**: Pre-filter files → classify relevant files only
**Pass 1**: File-level triage (which files in the diff are architecturally relevant?)
**Pass 2**: Full analysis on relevant files with service context

### File relevance heuristics

Architecturally relevant file patterns:
- `**/build.gradle*`, `**/pom.xml` (dependencies)
- `**/application*.yml`, `**/application*.properties` (config)
- `**/*Controller*`, `**/*Resource*` (API endpoints)
- `**/*Client*`, `**/*Feign*` (inter-service calls)
- `**/*Listener*`, `**/*Publisher*`, `**/*Consumer*` (messaging)
- `**/migration/**`, `**/*Entity*`, `**/*Model*` (data)
- `**/Dockerfile`, `**/.gitlab-ci.yml` (infrastructure)

### Structured output via tool_use

All LLM responses use Anthropic tool_use with Pydantic JSON schemas. Classification output:
```json
{
  "significant": "high" | "moderate" | "non-significant",
  "change_type": "[from taxonomy]",
  "confidence": "high" | "medium" | "borderline",
  "summary": "one line",
  "rationale": "one sentence WHY",
  "affected_services": ["service1", "service2"],
  "areas_of_impact": ["API surface", "data model", ...]
}
```

### Multi-agent perspectives

For multi-agent review, use 3 parallel LLM calls with different system prompts:
1. **API/Contract analyst**: Focus on external interfaces, DTOs, endpoint changes
2. **Dependency/Coupling analyst**: Focus on inter-service calls, shared state, transaction boundaries
3. **Risk/Security analyst**: Focus on security, data integrity, dead code, incomplete integration

Consensus = 2/3 agree on significance level. Disagreement triggers escalation criteria.

## Git Blame Strategy

**Decision**: Selective blame on architecturally relevant files only
**Approach**: For each file in an MR diff that passes the relevance filter, run `git blame -L <changed_lines>` to find the commit SHAs, then map those to merge commits via `git log --merges --grep="See merge request"`.
**Limitation**: Sample repos have only 2 commits — blame will be trivial. Documented in Assumptions.

## Dependencies Summary

| Package | Version | Purpose |
|---------|---------|---------|
| `anthropic` | latest | LLM calls |
| `python-gitlab` | latest | GitLab API |
| `click` | latest | CLI framework |
| `pydantic` | v2 | Data models, JSON schemas |
| `jinja2` | latest | Markdown template rendering |
| `tenacity` | latest | Retry logic for API/LLM calls |
| `pytest` | latest | Testing |
| `respx` | latest | HTTP mocking |
