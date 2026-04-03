# Implementation Plan: ADR Review Agent

**Branch**: `001-adr-review-agent` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-adr-review-agent/spec.md`

## Summary

Build an autonomous CLI agent that retrieves merge request data from GitLab, classifies architectural significance using multi-perspective LLM analysis, generates Architecture Decision Log entries and Architecture Decision Records, posts feedback on MRs, and commits results back to GitLab. The agent supports configurable trigger modes (per-MR, per-repo, per-group), tracks processing state for incremental re-analysis, and uses a multi-agent review pattern with escalation criteria for uncertain classifications.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: anthropic, python-gitlab, click, pydantic v2, jinja2, tenacity
**Storage**: JSON file (`.agent-state.json`) committed to GitLab repo
**Testing**: pytest + respx (HTTP mocking)
**Target Platform**: Linux/macOS CLI (WSL compatible)
**Project Type**: CLI tool
**Performance Goals**: Process 6 MRs in under 10 minutes (dominated by LLM latency)
**Constraints**: Prototype — no HA, no retry queues, no monitoring. Must be runnable from README in 30 minutes.
**Scale/Scope**: 6 sample MRs across 2 repos, extensible to arbitrary group size

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Signal Over Noise | Classification uses three-tier model with confidence markers. Borderline entries included per I.3. Dead code is a first-class signal. | PASS |
| II. Prototype Discipline | 8 dependencies, no framework. Multi-agent review justified (reduces false escalations, serves "agent design" criterion). Learning scoped to precedent lookup, not ML. | PASS |
| III. Documentation as Product | ADL/ADR output uses Jinja2 templates for consistent formatting. ADL extends existing table format. ADR follows Nygard + Alternatives + Confidence. | PASS |
| IV. Auditable Intelligence | Structured LLM output via tool_use. `--verbose` flag exposes classification reasoning. Prompts documented in design doc (FR-019). | PASS |
| V. GitLab-Native | All I/O through python-gitlab + git subprocess. MR comments posted via API. Pipeline status checked post-commit. | PASS |
| VI. Reproducibility | Click CLI with env-var fallback. setup.sh bootstraps environment. quickstart.md documents full flow. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/001-adr-review-agent/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── cli-interface.md # CLI commands, options, exit codes
│   └── llm-schemas.md  # Anthropic tool_use JSON schemas
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── __init__.py
├── cli.py                     # Click CLI entry point + subcommands
├── models/
│   ├── __init__.py
│   ├── gitlab_types.py        # MRAnalysisInput, FileDiff, Discussion, etc.
│   ├── classification.py      # SignificanceClassification, ChangeScope
│   ├── output.py              # ADLEntry, ADRDocument
│   └── state.py               # ProcessingState, MRState, EscalationPrecedent
├── services/
│   ├── __init__.py
│   ├── gitlab_client.py       # GitLab API wrapper (python-gitlab)
│   ├── git_ops.py             # Git subprocess wrapper (clone, blame, commit, push)
│   ├── classifier.py          # Multi-perspective LLM classification
│   ├── scope_analyzer.py      # Scope analysis skill (ticket refs, blame, deps)
│   ├── escalation.py          # Escalation criteria skill + precedent lookup
│   ├── adl_writer.py          # ADL table entry generation + markdown rendering
│   ├── adr_writer.py          # ADR document generation + markdown rendering
│   ├── mr_commenter.py        # MR comment posting strategy
│   ├── state_manager.py       # Processing state read/write/diff detection
│   └── pipeline_checker.py    # Post-commit pipeline status polling
├── templates/
│   ├── adl_entry.md.j2        # Jinja2 template for ADL table row
│   ├── adr_document.md.j2     # Jinja2 template for full ADR file
│   └── mr_comment.md.j2       # Jinja2 template for MR feedback comments
└── prompts/
    ├── api_contract.py        # System prompt: API/contract analysis perspective
    ├── dependency_coupling.py # System prompt: dependency/coupling perspective
    └── risk_security.py       # System prompt: risk/security perspective

tests/
├── conftest.py                # Shared fixtures (mock GitLab responses, sample diffs)
├── unit/
│   ├── test_classifier.py
│   ├── test_scope_analyzer.py
│   ├── test_escalation.py
│   ├── test_adl_writer.py
│   ├── test_adr_writer.py
│   └── test_state_manager.py
├── integration/
│   ├── test_review_mr.py      # End-to-end single MR flow
│   └── test_review_group.py   # End-to-end group flow
└── fixtures/
    ├── sample_diffs/          # Recorded MR diffs from sample repos
    └── sample_responses/      # Recorded GitLab API responses
```

**Structure Decision**: Single project (Option 1). The agent is a CLI tool with no frontend or separate backend. The `src/` directory uses a services-based architecture with Pydantic models as the contract between layers. Templates and prompts are first-class directories since they are core architectural artifacts (Constitution IV).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Multi-agent review (3 parallel LLM calls) | Reduces false escalations; serves "agent design" evaluation criterion | Single-agent classification has higher error rate on borderline cases; evaluator specifically looks for autonomous decision quality |
| Escalation precedent lookup | Avoids re-escalating the same pattern; makes agent smarter over time | Without it, every borderline case escalates every run — poor UX for the human reviewer |
