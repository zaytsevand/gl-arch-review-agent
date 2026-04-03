# Research: Architecture Baseline Snapshot

**Feature**: 002-architecture-snapshot | **Date**: 2026-04-03

## Key Decisions

### Codebase Scanning Strategy: LLM-assisted static analysis

**Decision**: Two-phase scan: (1) deterministic code parsing to extract structured facts (endpoints, entities, configs), then (2) LLM synthesis to produce a coherent narrative baseline document.
**Rationale**: Pure LLM analysis of raw source files is expensive and unreliable for large codebases. Extracting structured facts first (regex + AST-lite) and then having the LLM synthesize reduces token usage and improves accuracy.
**Alternatives**: Full LLM-only analysis (too expensive, unreliable at scale), pure rule-based (misses nuance, can't produce readable narrative)

### Reuse of Feature 001 Infrastructure

**Decision**: Extend the existing `src/services/` and `src/models/` from Feature 001 rather than creating parallel structures.
**Rationale**: Feature 002 needs the same GitLab client, git ops, state manager, escalation skill, and multi-agent review. Adding new scanner services alongside existing ones keeps the codebase cohesive.
**New modules**: `src/services/codebase_scanner.py`, `src/services/baseline_writer.py`, `src/services/baseline_detector.py`
**Extended modules**: `src/cli.py` (add `snapshot` command), `src/services/state_manager.py` (add baseline tracking)

### Baseline Document Template: Jinja2 with mandatory/optional sections

**Decision**: Use a Jinja2 template (`src/templates/baseline_document.md.j2`) with conditional sections. Mandatory: services inventory, communication patterns, tech stack, API contracts, data models, dependency graph. Optional: security posture, compliance, data flows, technical debt.
**Rationale**: Matches the prescribed-template-with-flexible-sections decision from clarifications. Jinja2 already used in Feature 001 for ADL/ADR.

### External Reference Following: Best-effort with timeout

**Decision**: When the scanner finds Confluence links, README URLs, or Jira ticket references in code/config, it attempts to fetch them via HTTP (for Confluence/web) or GitLab API (for linked issues). Failures are logged but don't block baseline generation.
**Rationale**: External references enrich the baseline but are not essential. A timeout + fallback approach respects Prototype Discipline (Constitution II).

### Baseline Staleness Detection: Heuristic based on ADL entry count and change types

**Decision**: After processing MRs, compare the number and types of high-significance ADL entries since the last baseline. If >3 high-significance entries OR any `infrastructure` or `new_dependency` change type, recommend refresh.
**Rationale**: Simple heuristic that's good enough for prototype. Avoids complex diff-against-baseline analysis.

## Dependencies (beyond Feature 001)

| Package | Purpose |
|---------|---------|
| (none new) | All needed packages already in Feature 001's pyproject.toml |
