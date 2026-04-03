# Implementation Plan: Architecture Baseline Snapshot

**Branch**: `002-architecture-snapshot` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-architecture-snapshot/spec.md`

## Summary

Extend the ADR Review Agent (Feature 001) with a codebase scanning capability that produces an Architecture Baseline Document. The baseline captures the current system state (services, communication patterns, APIs, data models, tech stack) and serves as a reference point for all ADL/ADR entries. Includes baseline detection in the main workflow, staleness detection, and refresh with version preservation.

## Technical Context

**Language/Version**: Python 3.11+ (same as Feature 001)
**Primary Dependencies**: Same as Feature 001 (anthropic, python-gitlab, click, pydantic v2, jinja2, tenacity) — no new deps
**Storage**: Same `.agent-state.json` + `ARCHITECTURE_BASELINE.md` in architecture-decisions repo
**Testing**: pytest + respx (same as Feature 001)
**Target Platform**: Linux/macOS CLI (WSL compatible)
**Project Type**: CLI tool extension (adds `snapshot` command to existing `adr-agent`)
**Constraints**: Builds on Feature 001 codebase. Must not break existing review-mr/review-repo/review-group commands.

## Constitution Check

| Principle | Gate | Status |
|-----------|------|--------|
| I. Signal Over Noise | Baseline focuses on architecturally relevant facts, not exhaustive code inventory. Optional sections omitted when no evidence found. | PASS |
| II. Prototype Discipline | Reuses Feature 001 infrastructure. No new deps. Scanner uses regex heuristics + LLM synthesis — no AST parsing library. | PASS |
| III. Documentation as Product | Baseline serves as onboarding doc. Prescribed template with mandatory sections. Human-readable narrative, not raw inventory. | PASS |
| IV. Auditable Intelligence | Multi-agent review for uncertain findings. Escalation with human-in-the-loop. Precedent lookup. | PASS |
| V. GitLab-Native | Scans via GitLab API (file contents) or git clone. Commits baseline to arch repo. | PASS |
| VI. Reproducibility | `snapshot` CLI command with same env var pattern. Baseline includes generation timestamp and scanned repos list. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/002-architecture-snapshot/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (extends Feature 001)

```text
src/
├── models/
│   └── baseline.py              # NEW: BaselineDocument, ServiceInventoryEntry, etc.
├── services/
│   ├── codebase_scanner.py      # NEW: Deep codebase scan
│   ├── baseline_writer.py       # NEW: LLM synthesis + Jinja2 rendering
│   ├── baseline_detector.py     # NEW: Existence check, content validation, staleness
│   └── state_manager.py         # EXTENDED: Baseline tracking
├── templates/
│   └── baseline_document.md.j2  # NEW: Jinja2 template
├── prompts/
│   └── baseline_synthesis.py    # NEW: System prompt for LLM synthesis
└── cli.py                       # EXTENDED: Add `snapshot` command + baseline detection
```

**Structure Decision**: Extends Feature 001's single-project structure. 3 new service modules, 1 new model file, 1 new template, 1 new prompt. CLI and state manager extended in-place.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| LLM synthesis for baseline | Raw facts produce an inventory, not a readable document. LLM turns facts into narrative. | Template-only approach produces boilerplate that fails SC-002 (onboarding readability). |
