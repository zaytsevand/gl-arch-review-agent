# Data Model: ADR Review Agent

**Feature**: 001-adr-review-agent | **Date**: 2026-04-03

## Core Entities

### MRAnalysisInput

Represents the raw data retrieved from GitLab for a single merge request.

| Field | Type | Description |
|-------|------|-------------|
| project_id | int | GitLab project ID |
| project_path | str | Full path (e.g., `group/order-service`) |
| mr_iid | int | MR internal ID within the project |
| title | str | MR title |
| description | str | MR description body |
| source_branch | str | Feature branch name |
| target_branch | str | Target branch (usually `main`) |
| state | str | `opened` or `merged` |
| author | str | MR author username |
| diffs | list[FileDiff] | File-level diffs |
| discussions | list[Discussion] | Review threads |
| pipeline_status | str | Latest pipeline status (`success`, `failed`, `pending`, etc.) |
| commits | list[CommitInfo] | Commits in the MR |
| web_url | str | MR URL for linking |

### FileDiff

| Field | Type | Description |
|-------|------|-------------|
| old_path | str | File path before change |
| new_path | str | File path after change |
| diff | str | Unified diff content |
| new_file | bool | Whether this is a newly created file |
| deleted_file | bool | Whether the file was deleted |
| renamed_file | bool | Whether the file was renamed |

### Discussion

| Field | Type | Description |
|-------|------|-------------|
| id | str | Discussion ID |
| notes | list[Note] | Messages in the thread |
| resolved | bool | Whether the thread is resolved |
| file_path | str | null | File path for inline discussions |
| line_number | int | null | Line number for inline discussions |

### Note

| Field | Type | Description |
|-------|------|-------------|
| author | str | Username |
| body | str | Comment text |
| created_at | datetime | Timestamp |
| system | bool | Whether it's a system-generated note |

### CommitInfo

| Field | Type | Description |
|-------|------|-------------|
| sha | str | Commit SHA |
| title | str | Commit message first line |
| message | str | Full commit message |
| authored_date | datetime | Commit date |

---

## Analysis Entities

### SignificanceClassification

Output of the classification LLM call. Used as Anthropic tool_use schema.

| Field | Type | Description |
|-------|------|-------------|
| significance | enum | `non_significant`, `moderate`, `high` |
| change_type | enum | From taxonomy: `api_change`, `new_dependency`, `schema_change`, `infrastructure`, `security`, `config_change`, `dead_code`, `contract_change` |
| confidence | enum | `high`, `medium`, `borderline` |
| summary | str | One-line summary (max 120 chars) |
| rationale | str | One sentence explaining WHY this is/isn't significant |
| affected_services | list[str] | Service names affected |
| areas_of_impact | list[str] | e.g., `["API surface", "inter-service contracts"]` |
| relevant_files | list[str] | Files that drove the classification |

### ChangeScope

Output of the scope analysis skill. Enriches classification with cross-repo context.

| Field | Type | Description |
|-------|------|-------------|
| ticket_references | list[TicketRef] | Ticket IDs found across repos |
| related_mrs | list[RelatedMR] | MRs in other repos sharing ticket references |
| documented_dependencies | list[str] | Dependencies from in-repo documentation |
| code_dependencies | list[str] | Dependencies detected from code analysis |
| blame_history | list[BlameEntry] | Prior MRs on the same changed lines |
| cross_repo_impact | bool | Whether the change affects multiple repos |

### TicketRef

| Field | Type | Description |
|-------|------|-------------|
| ticket_id | str | e.g., `PLAT-034` |
| source | str | Where found: `mr_title`, `mr_description`, `commit_message`, `code_comment` |
| project_path | str | Which repo it was found in |

### RelatedMR

| Field | Type | Description |
|-------|------|-------------|
| project_path | str | Repo path |
| mr_iid | int | MR IID |
| title | str | MR title |
| shared_ticket | str | The ticket ID they share |

### BlameEntry

| Field | Type | Description |
|-------|------|-------------|
| file_path | str | File that was blamed |
| line_range | str | Line range blamed |
| commit_sha | str | Commit that last touched these lines |
| mr_iid | int | null | MR that introduced the commit (if traceable) |
| age_days | int | How many days since that commit |

### MultiAgentReview

Result of parallel LLM analysis from multiple perspectives.

| Field | Type | Description |
|-------|------|-------------|
| perspectives | list[PerspectiveResult] | Individual agent results |
| consensus | bool | Whether agents agree on significance level |
| consensus_significance | enum | null | The agreed significance (null if no consensus) |
| consensus_confidence | enum | Aggregate confidence |
| escalation_triggered | bool | Whether escalation criteria were matched |
| escalation_reason | str | null | Why escalation was triggered |

### PerspectiveResult

| Field | Type | Description |
|-------|------|-------------|
| perspective | str | `api_contract`, `dependency_coupling`, `risk_security` |
| classification | SignificanceClassification | This agent's classification |

---

## Output Entities

### ADLEntry

Represents a single row in the Architecture Decision Log table.

| Field | Type | Description |
|-------|------|-------------|
| number | int | Auto-incrementing entry number |
| date | date | Date of the MR or analysis |
| service | str | Affected service name(s) |
| change_type | str | From taxonomy |
| confidence | str | `High`, `Medium`, `Borderline` |
| summary | str | One-line summary |
| rationale | str | One sentence WHY |
| adr_link | str | null | Relative path to ADR file, or `-` |

### ADRDocument

Full Architecture Decision Record file content.

| Field | Type | Description |
|-------|------|-------------|
| number | int | ADR number (matches ADL entry) |
| title | str | Decision title |
| date | date | Date |
| status | str | `Proposed` (always, for machine-generated) |
| confidence | str | `High`, `Medium`, `Borderline` |
| services | list[str] | Affected services |
| source_mr_urls | list[str] | MR URLs that triggered this ADR |
| context | str | What changed and why it matters |
| decision | str | What was done |
| alternatives | list[Alternative] | Considered alternatives |
| consequences | list[str] | Positive and negative impacts |

### Alternative

| Field | Type | Description |
|-------|------|-------------|
| name | str | Alternative approach |
| reason_rejected | str | Why not chosen |

---

## State Entities

### ProcessingState

Root object stored in `.agent-state.json`.

| Field | Type | Description |
|-------|------|-------------|
| version | str | Schema version (e.g., `1.0`) |
| last_run | datetime | Timestamp of last agent run |
| analyzed_mrs | dict[str, MRState] | Key: `{project_path}!{mr_iid}` |
| escalation_precedents | list[EscalationPrecedent] | Resolved escalation decisions for future lookup |
| adl_next_number | int | Next ADL entry number to assign |

### MRState

| Field | Type | Description |
|-------|------|-------------|
| project_path | str | Repo path |
| mr_iid | int | MR IID |
| last_commit_sha | str | Latest commit SHA at last analysis |
| description_hash | str | Hash of MR description at last analysis |
| discussion_count | int | Number of discussions at last analysis |
| pipeline_status | str | Pipeline status at last analysis |
| significance | str | Assigned significance level |
| adl_entry_number | int | null | Position in ADL (for updates) |
| adr_file | str | null | ADR filename (for updates) |

### EscalationPrecedent

| Field | Type | Description |
|-------|------|-------------|
| pattern_hash | str | Hash of the finding pattern (change_type + relevant_files signature) |
| human_decision | str | What the human decided |
| resolved_date | date | When it was resolved |
| context_summary | str | Brief context for matching |

---

## State Transitions

### MR Processing Lifecycle

```
Not Seen → Analyzing → Classified (non-significant | moderate | high)
                                     ↓ (if uncertain)
                              Multi-Agent Review → Consensus → Classified
                                                 → Disagreement → Escalated → Human Resolves → Classified
```

### Significance Level Transitions

```
non-significant → moderate (on re-analysis after MR changes)
non-significant → high (on re-analysis after MR changes)
moderate → high (on re-analysis or scope analysis reveals cross-repo impact)
high → high (ADR updated on re-analysis)
```

### ADL Entry Lifecycle

```
Created → Updated (on MR re-analysis)
         → Linked to ADR (when significance elevated to high)
```
