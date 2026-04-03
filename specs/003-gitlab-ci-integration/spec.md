# Feature Specification: GitLab CI Pipeline Integration

**Feature Branch**: `003-gitlab-ci-integration`  
**Created**: 2026-04-03  
**Status**: Draft  
**Input**: User description: "new feature: a gitlab ci templates to integrate agent to the CI pipeline"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Team Adds Agent to Their CI Pipeline via Include Template (Priority: P1)

A development team wants to automatically run the ADR Review Agent on every merge request in their service repositories. They add a single `include` directive to their `.gitlab-ci.yml` that references a reusable CI template provided by the agent. The template adds a pipeline stage that analyzes the MR, classifies architectural significance, updates the ADL/ADR, and posts feedback comments — all without the team writing custom CI jobs. The template is configurable via CI/CD variables for GitLab tokens, Anthropic keys, architecture-decisions repo path, and analysis options.

**Why this priority**: This is the core value — turning the agent from a manually-invoked CLI tool into an automated part of the development workflow. Every MR gets architectural review without human intervention.

**Independent Test**: Add the include directive to a sample service repo's `.gitlab-ci.yml`, open an MR, and verify the agent stage runs and produces ADL/ADR output + MR comments.

**Acceptance Scenarios**:

1. **Given** a service repo with the agent CI template included, **When** a developer opens a merge request, **Then** a pipeline stage runs the ADR review agent against that MR automatically.
2. **Given** the CI template is included with required variables set (GitLab token, Anthropic key, architecture repo path), **When** the pipeline runs, **Then** the agent classifies the MR, updates the ADL if significant, creates an ADR if highly significant, and posts feedback on the MR.
3. **Given** a merge request with only cosmetic changes, **When** the agent pipeline stage runs, **Then** it completes quickly, classifies the MR as non-significant, and does not modify the architecture-decisions repo or post comments.
4. **Given** the agent CI template is included but required CI/CD variables are not configured, **When** the pipeline runs, **Then** the agent stage fails gracefully with a clear error message indicating which variables are missing.

---

### User Story 2 - Team Configures Agent Behavior via CI/CD Variables (Priority: P2)

Teams have different needs: some want the agent to run on every MR, others only on MRs targeting specific branches. Some want dry-run mode in non-production branches. The CI template exposes configuration variables that control: which branches trigger analysis, whether to run in dry-run mode, the LLM model to use, and whether to auto-generate a baseline if missing.

**Why this priority**: Without configurability, teams can't adapt the agent to their workflow. One-size-fits-all templates get abandoned when they don't fit edge cases.

**Independent Test**: Configure different variable combinations in the service repo's CI/CD settings and verify the agent behaves accordingly.

**Acceptance Scenarios**:

1. **Given** the CI variable `ADR_AGENT_TARGET_BRANCHES` is set to `main,develop`, **When** an MR targets a branch not in that list, **Then** the agent stage is skipped.
2. **Given** the CI variable `ADR_AGENT_DRY_RUN` is set to `true`, **When** the pipeline runs, **Then** the agent analyzes the MR but does not commit changes or post comments.
3. **Given** the CI variable `ADR_AGENT_AUTO_BASELINE` is set to `true` and no baseline exists, **When** the pipeline runs, **Then** the agent generates a baseline before analyzing the MR.
4. **Given** all optional CI variables are left at their defaults, **When** the pipeline runs, **Then** the agent uses sensible defaults (analyze all target branches, real mode, auto-baseline enabled).

---

### User Story 3 - Group-Level Template Applied Across All Repos (Priority: P3)

An engineering organization wants to apply the agent to all service repositories in a GitLab group without modifying each repo's CI configuration individually. They configure a group-level CI include that applies the agent template to all projects in the group, with group-level CI/CD variables for shared configuration.

**Why this priority**: Scaling from one repo to many. Without group-level support, adoption requires changing every repo's CI config — a barrier for large organizations.

**Independent Test**: Configure the group-level CI include, open MRs in different repos within the group, and verify the agent runs on all of them.

**Acceptance Scenarios**:

1. **Given** the agent CI template is configured at the group level, **When** a developer opens an MR in any repo within the group, **Then** the agent pipeline stage runs without any per-repo configuration.
2. **Given** group-level CI/CD variables for tokens and architecture repo path, **When** a repo in the group has no additional agent configuration, **Then** it inherits the group settings and the agent functions correctly.
3. **Given** a repo has repo-level CI/CD variable overrides, **When** the agent pipeline runs, **Then** the repo-level variables take precedence over group-level settings.

---

### Edge Cases

- What happens when the agent pipeline stage times out (e.g., LLM is slow)?
- How does the pipeline behave when the architecture-decisions repo is inaccessible?
- What happens when two MRs in the same repo trigger the agent simultaneously (race condition on ADL updates)?
- How does the agent handle MRs in repos using languages/frameworks it doesn't recognize?
- What happens when the agent's changes to the architecture-decisions repo cause a merge conflict with another concurrent agent run? → Retry with rebase up to 3 attempts; log and exit gracefully if all fail.
- How does the pipeline behave when the Anthropic API rate limits are hit?

## Clarifications

### Session 2026-04-03

- Q: Should the agent CI stage block MR merge on failure? → A: Allow failure by default (advisory mode). Configurable to blocking via `ADR_AGENT_STRICT` variable. Progressive adoption: teams observe output first, then optionally enforce.
- Q: How should concurrent agent runs handle ADL updates? → A: Retry with rebase. On push conflict, pull --rebase and retry up to 3 attempts. Handles the common case without complex locking.
- Q: Where should the container image be published? → A: GitLab Container Registry within the agent's own project. GitLab-native, no external dependencies, accessible to any GitLab runner with project access.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST provide a reusable CI template file that teams can include in their `.gitlab-ci.yml` with a single `include` directive.
- **FR-002**: The CI template MUST define a pipeline stage that runs the ADR review agent against the current merge request.
- **FR-003**: The CI template MUST accept configuration via CI/CD variables: `ADR_AGENT_GITLAB_TOKEN` (required), `ADR_AGENT_ANTHROPIC_KEY` (required), `ADR_AGENT_ARCH_REPO` (required), `ADR_AGENT_MODEL` (optional), `ADR_AGENT_DRY_RUN` (optional), `ADR_AGENT_TARGET_BRANCHES` (optional), `ADR_AGENT_AUTO_BASELINE` (optional), `ADR_AGENT_STRICT` (optional, default false — when true, agent stage blocks MR merge).
- **FR-004**: The CI template MUST only run on merge request pipelines (not on branch pushes, tags, or scheduled pipelines).
- **FR-005**: The CI template MUST skip execution when required variables are missing and fail the stage with a descriptive error message listing the missing variables.
- **FR-006**: The CI template MUST support branch filtering — when `ADR_AGENT_TARGET_BRANCHES` is set, the agent only runs on MRs targeting those branches.
- **FR-007**: The CI template MUST support dry-run mode via `ADR_AGENT_DRY_RUN` — when enabled, the agent analyzes but does not commit or post comments.
- **FR-008**: The CI template MUST support group-level includes so it can be applied to all repos in a GitLab group via group CI/CD configuration.
- **FR-009**: The CI template MUST use a container image that has the ADR review agent pre-installed with all dependencies, so no installation step is needed at pipeline runtime.
- **FR-010**: The CI template MUST set a reasonable timeout for the agent stage (configurable, default: 10 minutes) to prevent runaway pipelines.
- **FR-011**: The agent MUST exit with a non-zero code only on configuration errors (missing required variables). Classification results (including non-significant) MUST always exit with code 0. The CI template MUST set `allow_failure: true` by default (advisory mode). When `ADR_AGENT_STRICT` is set to `true`, the template switches to `allow_failure: false`, making the agent stage blocking for MR merge.
- **FR-012**: When the agent's push to the architecture-decisions repo fails due to a merge conflict (concurrent agent runs), the agent MUST pull with rebase and retry the push, up to 3 attempts. If all retries fail, the agent MUST log the conflict and exit without blocking the MR.
- **FR-013**: The CI template MUST include documentation (inline comments and a README section) explaining how to set it up, what variables to configure, and what the agent does.

### Key Entities

- **CI Template**: A reusable `.gitlab-ci.yml` fragment that defines the ADR agent pipeline stage, including job definition, variable declarations, rules for when to run, and script commands.
- **Container Image**: A pre-built image containing the ADR agent CLI tool and all dependencies, published to the GitLab Container Registry within the agent's own project. Referenced by the CI template via the registry URL.
- **CI/CD Variables**: GitLab project or group-level variables that configure the agent's behavior — tokens, model selection, target branches, dry-run mode.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A team can add the agent to their CI pipeline with 3 or fewer lines of CI configuration (the include directive + variable references).
- **SC-002**: The agent pipeline stage completes within 10 minutes for a single MR with up to 50 changed files.
- **SC-003**: When required variables are missing, the pipeline fails within 10 seconds with a human-readable error listing all missing variables.
- **SC-004**: The CI template works without modification for both project-level and group-level includes.
- **SC-005**: A team can go from zero configuration to a working ADR agent pipeline in under 15 minutes following only the setup documentation.

## Assumptions

- GitLab CI/CD is the team's pipeline platform (not GitHub Actions, Jenkins, etc.).
- The container image is published to the GitLab Container Registry within the agent's own project, accessible by any GitLab runner with project access.
- GitLab runners support Docker executor (standard for gitlab.com and most self-hosted instances).
- The CI/CD variables for tokens are configured as masked/protected variables in GitLab's project or group settings.
- The agent's container image is built and published as a separate build/release step (not part of this feature's runtime).
- This feature depends on Feature 001 (ADR Review Agent) and Feature 002 (Architecture Baseline Snapshot) being implemented — the CI template invokes the existing `adr-agent` CLI.
