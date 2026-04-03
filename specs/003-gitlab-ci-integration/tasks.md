# Tasks: GitLab CI Pipeline Integration

**Input**: Design documents from `/specs/003-gitlab-ci-integration/`
**Prerequisites**: plan.md (required), spec.md (required), contracts/ci-variables.md
**Depends on**: Features 001 + 002 must be implemented first

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Create `ci/` directory structure

- [x] T001 Create `ci/` directory at repository root
- [x] T002 [P] Extend push retry logic in `src/services/git_ops.py` — wrap `push()` with conflict detection: if push fails due to remote changes, run `git pull --rebase origin <branch>`, then retry push, up to 3 attempts. Log each retry. After 3 failures, raise with descriptive error.

**Checkpoint**: `ci/` directory exists, git_ops push retry works.

---

## Phase 2: User Story 1 — CI Template for MR Pipeline (Priority: P1)

**Goal**: Provide a reusable CI template that teams include to automatically run the ADR agent on every MR.

**Independent Test**: Include template in sample service repo, open MR, verify agent stage runs.

### Implementation for User Story 1

- [x] T003 [US1] Create Dockerfile in `ci/Dockerfile` — multi-stage build: stage 1 (`python:3.11-slim` base) installs the adr-agent package with `pip install .`; stage 2 copies the installed package into a clean slim image. Entry point: `adr-agent`. Target image size: <500MB.
- [x] T004 [US1] Create reusable CI template in `ci/adr-agent.gitlab-ci.yml` — define `adr-review` job in an `architecture-review` stage. Job configuration:
  - `image`: reference to the agent container image in GitLab Container Registry
  - `rules`: only run on `merge_request_event` pipelines
  - `variables`: declare all CI/CD variables from contracts/ci-variables.md with defaults
  - `before_script`: validate required variables (`ADR_AGENT_GITLAB_TOKEN`, `ADR_AGENT_ANTHROPIC_KEY`, `ADR_AGENT_ARCH_REPO`) — exit 1 with descriptive error if any missing
  - `script`: run `adr-agent review-mr "$CI_PROJECT_PATH!$CI_MERGE_REQUEST_IID"` with `--gitlab-url $CI_SERVER_URL --gitlab-token $ADR_AGENT_GITLAB_TOKEN --anthropic-key $ADR_AGENT_ANTHROPIC_KEY --arch-repo $ADR_AGENT_ARCH_REPO` plus optional flags from variables
  - `allow_failure: true` by default
  - `timeout`: `$ADR_AGENT_TIMEOUT` or 10m default
  - Inline comments explaining every section
- [x] T005 [US1] Add branch filtering logic to CI template in `ci/adr-agent.gitlab-ci.yml` — in `rules:`, check if `$ADR_AGENT_TARGET_BRANCHES` is set; if so, only run when `$CI_MERGE_REQUEST_TARGET_BRANCH_NAME` matches one of the comma-separated values. If unset, run on all target branches.
- [x] T006 [US1] Add dry-run and verbose flag wiring in `ci/adr-agent.gitlab-ci.yml` — in `script:`, conditionally append `--dry-run` when `$ADR_AGENT_DRY_RUN == "true"` and `--verbose` when `$ADR_AGENT_VERBOSE == "true"`.
- [x] T007 [US1] Add auto-baseline flag wiring in `ci/adr-agent.gitlab-ci.yml` — when `$ADR_AGENT_AUTO_BASELINE == "false"`, pass a flag to skip baseline auto-generation (default: enabled).

**Checkpoint**: CI template is complete with all variable wiring, branch filtering, and inline documentation. Can be included by a service repo.

---

## Phase 3: User Story 2 — Configurable Agent Behavior (Priority: P2)

**Goal**: Teams configure agent behavior via CI/CD variables without modifying the template.

**Independent Test**: Set different variable combinations in GitLab project settings, verify behavior changes.

### Implementation for User Story 2

- [x] T008 [US2] Add strict mode support to CI template in `ci/adr-agent.gitlab-ci.yml` — when `$ADR_AGENT_STRICT == "true"`, set `allow_failure: false` (use GitLab CI `rules:` with `allow_failure` attribute or a conditional job definition). Document in inline comments.
- [x] T009 [US2] Add variable validation script as `ci/validate-vars.sh` — standalone shell script called by `before_script` that checks all required variables, prints a formatted error table of missing ones, and exits 1 if any are missing. Makes the error message human-readable.
- [x] T010 [US2] Add model selection wiring in `ci/adr-agent.gitlab-ci.yml` — pass `--model $ADR_AGENT_MODEL` when the variable is set (default: `claude-sonnet-4-6`).

**Checkpoint**: All CI/CD variables from contracts/ci-variables.md are wired and documented. Strict mode toggles allow_failure. Missing variables produce clear error.

---

## Phase 4: User Story 3 — Group-Level Template (Priority: P3)

**Goal**: Apply the agent to all repos in a GitLab group without per-repo CI changes.

**Independent Test**: Configure group-level include, open MRs in different repos, verify agent runs on all.

### Implementation for User Story 3

- [x] T011 [US3] Verify group-level include compatibility in `ci/adr-agent.gitlab-ci.yml` — ensure the template works when included via group-level CI/CD configuration (`include: project`). Verify `$CI_PROJECT_PATH` and `$CI_MERGE_REQUEST_IID` are available in group-level includes. Document group-level setup instructions in template comments.
- [x] T012 [US3] Document group-level setup in README — add a "Group-Level Setup" section to `README.md` explaining: how to configure group CI/CD includes, where to set group-level variables, and how repo-level overrides work.

**Checkpoint**: Template works identically for project-level and group-level includes. README documents both setups.

---

## Phase 5: Container Image Build Pipeline

**Purpose**: CI pipeline to build and publish the agent container image to GitLab Container Registry.

- [x] T013 Create image build pipeline in `ci/.gitlab-ci.yml` — define a pipeline that: builds the Docker image from `ci/Dockerfile`, tags it with `$CI_COMMIT_TAG` (for releases) or `latest` (for main branch), pushes to `$CI_REGISTRY_IMAGE`. Runs on tag pushes and main branch merges.
- [x] T014 [P] Update `ci/adr-agent.gitlab-ci.yml` image reference to use the GitLab Container Registry path (e.g., `$CI_REGISTRY/group/adr-review-agent:latest`).

**Checkpoint**: Pushing a tag builds and publishes the container image. CI template references the published image.

---

## Phase 6: Polish & Documentation

**Purpose**: Documentation and validation

- [x] T015 [P] Add CI integration section to `README.md` — document: quick start (3-line include), variable reference table, branch filtering, dry-run, strict mode, group-level setup, troubleshooting
- [x] T016 [P] Add inline documentation to all CI template variables in `ci/adr-agent.gitlab-ci.yml` — every variable must have a comment explaining purpose, type, and default
- [x] T017 Validate container image: build image from `ci/Dockerfile`, run `docker run <image> adr-agent --help` and verify it produces expected CLI help output with all 4 commands (review-mr, review-repo, review-group, snapshot)
- [x] T018 Validate end-to-end: include template in sample order-service `.gitlab-ci.yml`, set required variables, open an MR, verify pipeline runs agent stage and produces output

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies beyond Features 001+002 being implemented
- **US1 Template (Phase 2)**: Depends on Phase 1 (ci/ directory, push retry)
- **US2 Configuration (Phase 3)**: Depends on US1 (template must exist to configure)
- **US3 Group-Level (Phase 4)**: Depends on US1 (template must work at project level first)
- **Image Build (Phase 5)**: Depends on US1 (Dockerfile + template)
- **Polish (Phase 6)**: Depends on all phases

### Parallel Opportunities

```
T001 (ci/ dir) ─┐
T002 (push retry) ┘ parallel

T003 (Dockerfile) ─┐
T004 (CI template) ─┤ T003 first, then T004-T007 sequential
T005 (branch filter) ┤
T006 (dry-run/verbose)┤
T007 (auto-baseline) ─┘

T008 (strict mode) ─┐
T009 (validate vars) ┤ parallel
T010 (model select) ─┘

T013 (build pipeline) ─┐
T014 (image ref) ──────┘ sequential

T015 (README) ─┐
T016 (comments) ┘ parallel
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1: Setup (ci/ dir + push retry)
2. Phase 2: CI template with basic variable support
3. **STOP and VALIDATE**: Include in sample repo, open MR, verify agent runs
4. This alone enables automated ADR review on MRs

### Incremental Delivery

1. Setup → Foundation ready
2. US1 → Basic CI template works (MVP)
3. US2 → Full variable configurability
4. US3 → Group-level deployment
5. Image Build → Automated container publishing
6. Polish → Documentation complete

---

## Notes

- This feature is primarily configuration (YAML, Dockerfile, shell script) — not Python code
- Only code change is extending `git_ops.py` with push retry (T002)
- Total: 18 tasks across 6 phases
- Small, focused feature — should be implementable in a single session
