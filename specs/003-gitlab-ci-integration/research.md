# Research: GitLab CI Pipeline Integration

**Feature**: 003-gitlab-ci-integration | **Date**: 2026-04-03

## Key Decisions

### CI Template Distribution: GitLab CI `include` with remote file

**Decision**: Distribute the CI template as a YAML file in the agent's own repository, consumed via `include: remote` or `include: project`.
**Rationale**: GitLab supports `include: project` (same instance) and `include: remote` (URL). Since the agent lives in a GitLab project, `include: project` is simplest — no hosting, no versioning headaches, same access controls.
**Alternatives**: Published CI component (GitLab CI catalog — still beta), npm/pip package with CI template, raw URL include. All add complexity for no benefit at prototype stage.

### Container Image Strategy: Multi-stage Dockerfile

**Decision**: Single Dockerfile using multi-stage build: build stage installs deps, runtime stage copies installed package. Published to GitLab Container Registry via the agent project's own CI pipeline.
**Rationale**: Multi-stage keeps image small. GitLab Container Registry is co-located, no external accounts needed.
**Alternatives**: Pre-built image on Docker Hub (wider reach but external dependency), build at runtime in each pipeline (slow, violates SC-002's 10-minute constraint).

### Retry Strategy for Push Conflicts

**Decision**: Extend `git_ops.py` `push()` method with retry-on-conflict: catch push failure, run `git pull --rebase`, re-push, up to 3 attempts.
**Rationale**: Simple, deterministic, covers the common case of concurrent agent runs. No locking infrastructure needed.
**Alternatives**: Distributed lock via GitLab API (complex, overkill), queue-based serial execution (requires infrastructure).

### Branch Filtering: GitLab CI `rules` with variable

**Decision**: Use `rules:` with `$CI_MERGE_REQUEST_TARGET_BRANCH_NAME` to match against `ADR_AGENT_TARGET_BRANCHES`. Default: run on all target branches.
**Rationale**: Native GitLab CI mechanism, no custom scripting needed.

### Allow Failure: Dynamic via variable

**Decision**: Use `allow_failure` with a variable reference. When `ADR_AGENT_STRICT=true`, set `allow_failure: false`.
**Rationale**: GitLab CI supports `allow_failure` as a job attribute. Dynamic toggle via variable provides the progressive adoption pattern.

## No New Dependencies

This feature adds only configuration files (YAML, Dockerfile) — no Python packages or code dependencies beyond what Features 001 and 002 already provide.
