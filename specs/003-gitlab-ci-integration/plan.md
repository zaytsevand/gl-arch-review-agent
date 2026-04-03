# Implementation Plan: GitLab CI Pipeline Integration

**Branch**: `003-gitlab-ci-integration` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-gitlab-ci-integration/spec.md`

## Summary

Provide reusable GitLab CI template files, a Dockerfile for the agent container image, and a CI pipeline to build/publish the image. Teams include the template in their `.gitlab-ci.yml` to automatically run the ADR review agent on every merge request. Configurable via CI/CD variables for tokens, model, target branches, dry-run, strict mode, and auto-baseline.

## Technical Context

**Language/Version**: YAML (GitLab CI), Dockerfile (multi-stage, Python 3.11-slim base)
**Primary Dependencies**: Features 001 + 002 (the `adr-agent` CLI tool)
**Storage**: N/A (CI templates are static files)
**Testing**: Manual integration test — include template in sample repo, open MR, verify pipeline
**Target Platform**: GitLab CI/CD (gitlab.com + self-hosted)
**Project Type**: CI/CD configuration + container image
**Performance Goals**: Agent stage completes in under 10 minutes (SC-002)
**Constraints**: Single `include` directive for adoption. Container image must be <500MB.
**Scale/Scope**: Template works for any number of repos in a GitLab group

## Constitution Check

| Principle | Gate | Status |
|-----------|------|--------|
| I. Signal Over Noise | Agent runs only on MR pipelines, not branch pushes. Configurable target branches. Non-significant MRs exit cleanly. | PASS |
| II. Prototype Discipline | 3 new files (CI template, Dockerfile, build pipeline). No framework. Minimal config surface. | PASS |
| III. Documentation as Product | CI template has inline comments explaining every variable and rule. README section documents setup. | PASS |
| IV. Auditable Intelligence | Verbose mode available via `ADR_AGENT_VERBOSE` variable. Pipeline logs show classification reasoning. | PASS |
| V. GitLab-Native | CI template, GitLab Container Registry, CI/CD variables — everything within GitLab ecosystem. | PASS |
| VI. Reproducibility | Template is versioned in the agent repo. Container image tagged by version. Setup docs in README. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/003-gitlab-ci-integration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── contracts/
│   └── ci-variables.md  # CI/CD variable contract
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
ci/
├── adr-agent.gitlab-ci.yml     # Reusable CI template (teams include this)
├── Dockerfile                   # Multi-stage build for agent container image
└── .gitlab-ci.yml              # Build pipeline for the container image itself

src/services/
└── git_ops.py                  # EXTENDED: add retry-on-conflict to push()
```

**Structure Decision**: New `ci/` directory at repo root for all CI-related files. Extends `src/services/git_ops.py` with push retry logic. No other source changes needed — the CI template invokes the existing `adr-agent` CLI.

## Complexity Tracking

> No violations — this feature is 3 config files + 1 minor code extension.
