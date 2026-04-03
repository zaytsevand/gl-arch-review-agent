# Feature Specification: Architecture Decision Review Agent

**Feature Branch**: `001-adr-review-agent`  
**Created**: 2026-04-03  
**Status**: Draft  
**Input**: User description: "use t.muratshin/assignment.md to infer requirements for this project"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent Analyzes MR Diffs and Classifies Architectural Significance (Priority: P1)

An autonomous agent monitors merge requests across GitLab repositories, configurable at per-MR, per-repo, or per-group scope. For each MR, the agent retrieves the diff and invokes a separate scope analysis skill to determine cross-repo impact (ticket references, dependency documentation, code-level dependencies), then analyzes the combined data to determine whether the change is architecturally significant. Architecturally significant changes include: new API endpoints or API versioning, new inter-service communication patterns, introduction of new infrastructure (WebSocket, messaging), state machine or workflow changes, data model changes, cross-service contract changes, build system migrations, security-relevant changes, and dead code or incomplete integration paths (architectural violations/threats that indicate unfinished or abandoned patterns). Trivial changes (typo fixes, comment edits, variable renames) are classified as non-significant and skipped.

**Why this priority**: This is the core intelligence of the agent. Without accurate classification, the entire system produces noise or misses important changes. Everything downstream depends on this.

**Independent Test**: Can be tested by pointing the agent at the 6 sample MRs and verifying it correctly classifies each one (e.g., `fix/ORD-142-logging-typos` as low-significance, `feature/PLAT-034-api-v2-workflow-rework` as high-significance).

**Acceptance Scenarios**:

1. **Given** a merge request with only cosmetic changes (typo fixes, comment edits, variable renames), **When** the agent analyzes the diff, **Then** it classifies the change as architecturally non-significant and does not produce an ADL entry. If review comments discuss architectural topics not present in the diff (e.g., a build migration that already landed on main), the agent MUST log this reasoning (Auditable Intelligence) but not attribute the architectural change to this MR.
2. **Given** a merge request introducing a new API version with state machine, workflow changes, and cross-service refund integration, **When** the agent analyzes the diff, **Then** it classifies the change as architecturally significant and identifies the specific areas of impact (API surface, inter-service contracts, data flow).
3. **Given** a merge request that adds WebSocket infrastructure to a service, **When** the agent analyzes the diff, **Then** it classifies the change as architecturally significant with a notation about the new communication pattern.
4. **Given** a merge request that extracts validation logic into a dedicated component without changing external contracts, **When** the agent analyzes the diff, **Then** it classifies the change as moderate significance (internal refactoring with design pattern implications).

---

### User Story 2 - Agent Maintains Architecture Decision Log (Priority: P1)

When the agent identifies an architecturally significant change, it creates a concise entry in `ARCHITECTURE_DECISION_LOG.md` in the architecture-decisions repository. Each entry provides enough context for a reader to understand what changed and why at a glance. The log accumulates entries over time, forming a chronological record of architectural evolution.

**Why this priority**: The ADL is the primary deliverable — it's the living document that future team members will consult. Tied with P1 because without output, the classification is useless.

**Independent Test**: Can be tested by running the agent against MRs and verifying that `ARCHITECTURE_DECISION_LOG.md` contains well-structured entries for significant changes only, with no entries for trivial changes.

**Acceptance Scenarios**:

1. **Given** a merge request classified as architecturally significant, **When** the agent processes it, **Then** a new entry is appended to `ARCHITECTURE_DECISION_LOG.md` that includes: date, affected service(s), confidence level (High / Medium / Borderline), a summary of what changed, and the rationale/context for the change.
2. **Given** a merge request classified as non-significant, **When** the agent finishes analysis, **Then** no entry is added to the ADL.
3. **Given** multiple significant MRs processed sequentially, **When** the agent processes each one, **Then** entries appear in chronological order and the log remains well-formatted and readable.
4. **Given** a significant MR that also has a detailed ADR created, **When** the ADL entry is written, **Then** it includes a link to the corresponding ADR file.
5. **Given** a previously non-significant MR that gains new architecturally significant commits or review comments, **When** the agent re-analyzes it, **Then** a new ADL entry is created and the processing state is updated to reflect the new significance level.

---

### User Story 3 - Agent Creates Detailed ADR Files for High-Impact Changes (Priority: P2)

For changes that are particularly impactful (e.g., new API versions, new communication patterns, cross-service contract changes), the agent creates a separate, detailed Architecture Decision Record file in the `adr/` directory. The ADR provides in-depth context including the decision made, alternatives considered, consequences, and affected services.

**Why this priority**: ADRs add depth beyond the ADL summary. Important for major decisions, but the ADL alone provides the minimum viable documentation.

**Independent Test**: Can be tested by running the agent against the most impactful MRs (e.g., PLAT-034 V2 rework, PAY-095 WebSocket) and verifying standalone ADR files are created with meaningful content.

**Acceptance Scenarios**:

1. **Given** a merge request with high architectural impact (e.g., introducing API V2 with state machine), **When** the agent processes it, **Then** a new ADR file is created in `adr/` with a descriptive filename and structured content covering: context, decision, consequences, and affected services.
2. **Given** a merge request with moderate significance (e.g., validation extraction), **When** the agent processes it, **Then** only an ADL entry is created; no separate ADR file is generated.
3. **Given** a newly created ADR file, **When** the agent commits it, **Then** the corresponding ADL entry links to the ADR file.

---

### User Story 4 - Agent Commits Results to GitLab (Priority: P2)

The agent commits its ADL updates and any ADR files back to the architecture-decisions repository in GitLab. Commits have meaningful messages that reference the analyzed MR.

**Why this priority**: Without committing back, the documentation exists only locally. Essential for the agent to be useful in a team workflow, but secondary to the analysis quality.

**Independent Test**: Can be tested by running the agent and verifying that commits appear in the architecture-decisions repo on GitLab with correct content and meaningful commit messages.

**Acceptance Scenarios**:

1. **Given** the agent has generated an ADL entry and an ADR file, **When** it commits to GitLab, **Then** the commit includes both the updated ADL file and the new ADR file with a descriptive commit message referencing the source MR.
2. **Given** the agent has generated only an ADL entry (no ADR), **When** it commits to GitLab, **Then** the commit includes only the updated ADL file.
3. **Given** a network or authentication failure during commit, **When** the agent attempts to push, **Then** it reports the error clearly and does not lose the generated content.
4. **Given** the LLM is unavailable while analyzing one MR in a batch, **When** the agent encounters the failure, **Then** it logs a warning identifying the skipped MR and continues processing the remaining MRs, committing partial results.
5. **Given** the agent has classified an MR as architecturally significant, **When** it posts feedback on the MR, **Then** it autonomously chooses between inline comments on specific lines, a summary comment linking to the ADL/ADR, or both — based on whether the architectural impact is localized or broad.

---

### User Story 5 - Agent Provides a Runnable Demo Against Sample MRs (Priority: P3)

The agent can be pointed at the provided sample repositories (order-service with 3 MRs, payment-service with 3 MRs) and produce a complete ADL and set of ADR files. The demo is reproducible using the provided `setup.sh` script to bootstrap the GitLab environment.

**Why this priority**: The demo is an evaluation artifact. It validates the agent works end-to-end but is not core functionality.

**Independent Test**: Can be tested by running `setup.sh` to create the GitLab environment, running the agent, and verifying the resulting ADL and ADR files in the architecture-decisions repo.

**Acceptance Scenarios**:

1. **Given** a freshly created GitLab environment (via `setup.sh`), **When** the agent is run against all 6 MRs, **Then** the architecture-decisions repo contains a populated ADL and appropriate ADR files.
2. **Given** the demo has completed, **When** an evaluator reads the ADL, **Then** they can understand the architectural evolution of the two services without reading the MR diffs.

---

### Edge Cases

- What happens when an MR has no diff (empty MR or draft with no commits)?
- How does the agent handle an MR that modifies both services simultaneously (cross-repo change)?
- What happens when the architecture-decisions repo has a merge conflict (e.g., concurrent ADL updates)?
- How does the agent behave when GitLab API rate limits are hit?
- What happens when an MR diff is extremely large (thousands of lines)?
- How does the agent handle MRs with review comments that provide additional architectural context beyond the diff itself?
- What happens when a previously non-significant MR becomes significant after new commits or review comments are added?
- How does the agent handle an ADL entry update when the significance level changes (e.g., moderate → high, now requiring an ADR)?

## Clarifications

### Session 2026-04-03

- Q: How should the agent handle re-processing the same MR? → A: Re-analyze MRs on any change since last run. Tracked changes include: new/updated threads and comments, pipeline run state changes, new commits, and description edits. The agent updates existing ADL/ADR entries rather than creating duplicates.
- Q: What should the agent do if the LLM is unavailable or returns an unusable response? → A: Skip the failed MR, log a warning, and continue processing remaining MRs. Partial results are acceptable; skipped MRs will be picked up on the next run.
- Q: What unit of work does a single agent run process? → A: Configurable via CLI — supports per-MR, per-repo, and per-group modes. Additionally, a separate "scope analysis" skill determines the cross-repo impact of a change dynamically by: following ticket references in MRs/code/commits, checking other repos for the same ticket, reading in-repo dependency documentation, and analyzing code for undocumented dependencies.
- Q: Should the agent analyze open MRs, merged MRs, or both? → A: Both, configurable via CLI filter, defaults to both. Additionally, the agent uses git blame on changed lines to trace prior MRs that touched the same code, pulling those MRs as supplementary context for deeper analysis.
- Q: Should the agent post findings back as MR comments? → A: Yes. The agent autonomously decides the comment strategy per MR: inline comments on architecturally significant lines when the feedback is localized, a summary comment linking to the ADL/ADR entry when the change has broad impact, or both when warranted. The agent judges which approach best serves the MR author.

### Input Data Analysis — 2026-04-03

- Q: ADL has pre-existing table format — how to handle? → A: Extend the existing table with additional columns (Confidence, Rationale) rather than replacing the format.
- Q: PLAT-034 spans both repos — one entry or two? → A: Two separate ADL entries (one per MR) for traceability, plus one shared ADR covering the cross-service architectural decision, linked from both entries.
- Q: Git blame limited on shallow sample repos? → A: Acknowledge as demo limitation in Assumptions. Implement fully; note it demonstrates value on mature repos.
- Q: architecture-decisions repo has markdown linting CI? → A: Agent reads target repo CI/linting config and adapts output. After committing, agent checks pipeline status to verify its changes didn't break CI.
- Q: Review comments have resolved/unresolved threads, external refs? → A: Weight resolved discussions higher (team consensus). Flag unresolved ones as open architectural questions in ADL/ADR.
- Q: Dead code / incomplete integration as architectural signal? → A: Yes — dead code is an architectural violation/threat. Agent MUST weight and acknowledge it as a first-class significance signal.
- Q: ORD-142 has hidden architectural discussion in review comments but cosmetic diff? → A: Classify as non-significant (diff is truth). Log reasoning about review comment context per Auditable Intelligence.
- Q: Feature branches have wrong build tool in README? → A: Agent flags documentation/build inconsistencies as low-severity MR comments. Not ADL-worthy, but worth surfacing to the developer.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Agent MUST retrieve merge request data from GitLab repositories, including: diff, metadata, description, review threads/comments, pipeline run state, and commit history.
- **FR-002**: Agent MUST analyze each MR diff and classify it into one of three significance levels: non-significant (no output), moderately significant (ADL entry only), or highly significant (ADL entry + ADR file).
- **FR-003**: Agent MUST generate concise, readable ADL entries that include: date, affected service(s), confidence level (High / Medium / Borderline), summary of the architectural change, and rationale/context. Borderline entries MUST be included per Constitution I.3 (err toward inclusion) and clearly marked as such.
- **FR-004**: Agent MUST detect and respect the existing ADL file format. If the file contains a pre-existing table structure, the agent MUST extend it with additional columns needed for its output (e.g., Confidence, Rationale) rather than replacing the format. New entries MUST be appended without overwriting or corrupting previous entries.
- **FR-005**: Agent MUST create detailed ADR files in the `adr/` directory for high-impact changes, with structured content (context, decision, consequences, affected services).
- **FR-006**: Agent MUST link ADR files from corresponding ADL entries when both are created. When multiple MRs across different repos share a ticket reference (e.g., PLAT-034 in both order-service and payment-service), the agent MUST create separate ADL entries per MR for traceability, but produce a single shared ADR that covers the cross-service architectural decision holistically, linked from both ADL entries.
- **FR-007**: Agent MUST commit all generated documentation (ADL updates, ADR files) back to the architecture-decisions repository in GitLab with meaningful commit messages. Before generating output, the agent MUST read the target repository's CI configuration and linting rules (e.g., `.gitlab-ci.yml`, `.markdownlint.json`) and adapt its markdown output to comply. After committing, the agent MUST check the pipeline status to verify its changes did not break CI, and report any failures.
- **FR-008**: Agent MUST support three trigger modes via CLI: per-MR (single MR URL/ID), per-repo (all open MRs in a repo), and per-group (all open MRs across all repos in a GitLab group). An MR state filter (open, merged, or both) MUST be configurable, defaulting to both.
- **FR-009**: Agent MUST incorporate MR review comments as supplementary context for analysis, not rely solely on the raw diff. The agent MUST weight resolved discussions higher than unresolved ones (resolved threads represent team consensus on an architectural direction). Unresolved discussions MUST be flagged as open architectural questions in ADL/ADR entries.
- **FR-010**: Agent MUST track which MRs have been previously analyzed and detect changes since the last run, including: new commits, description edits, new/updated review threads, and pipeline state changes. Processing state MUST be persisted as a state file in the architecture-decisions repository (e.g., `.agent-state.json`), committed alongside ADL/ADR updates, so the agent's memory is reproducible and inspectable.
- **FR-011**: When an already-processed MR has changed, the agent MUST re-analyze it and update the existing ADL entry (and ADR file if applicable) rather than creating duplicate entries.
- **FR-012**: The agent MUST include a separate scope analysis skill that determines the cross-repo impact of a change by: (a) following ticket/issue references in MR titles, descriptions, code, and commits; (b) checking other repos in the group for the same ticket reference; (c) reading in-repo dependency documentation; (d) analyzing code for undocumented dependencies (e.g., shared API contracts, imported clients); (e) using git blame on changed lines to identify prior MRs that touched the same code, and pulling those MRs as supplementary historical context.
- **FR-013**: The scope analysis skill MUST feed its findings into the significance classification — a change that touches multiple repos or crosses service boundaries is inherently more architecturally significant. Historical context from git blame (prior MRs on the same lines) MUST inform whether a change represents a pattern shift or continuation of existing direction.
- **FR-014**: For MRs classified as moderately or highly significant, the agent MUST post feedback directly on the MR, autonomously choosing the comment strategy: inline comments on architecturally significant lines when feedback is localized, a summary comment linking to the ADL/ADR entry when the change has broad impact, or both when warranted. For obviously trivial MRs, the agent MUST NOT post comments (Signal Over Noise). For borderline MRs classified as non-significant, the agent MAY post a brief note explaining why no architectural documentation was generated (Auditable Intelligence). Regardless of significance level, the agent MAY post low-severity inline comments flagging documentation inconsistencies (e.g., README referencing wrong build tool) when detected — these are quality observations, not architectural documentation.
- **FR-015**: When the LLM is unavailable or returns an unusable response for a given MR, the agent MUST skip that MR, log a warning with the MR identifier, and continue processing the remaining MRs.
- **FR-016**: The agent MUST integrate with the shared escalation criteria skill and multi-agent review pattern (defined in Feature 002). For MR analysis, uncertain classifications MUST be submitted to multi-agent review before finalization. When agents disagree or escalation criteria are matched, the finding is raised as a review comment on the MR and blocked until a human resolves it. When agents reach consensus, the classification is finalized autonomously.
- **FR-017**: The agent MUST consult the escalation precedent records (stored in `.agent-state.json`) before escalating — if a human previously resolved an equivalent pattern, the agent MUST apply that decision autonomously.
- **FR-018**: Agent MUST include a README with setup and usage instructions.
- **FR-019**: Agent MUST include a design document explaining approach, decisions, and trade-offs. The design document MUST include prompt design rationale and the prompts used for classification and content generation, as these are core architectural artifacts per Constitution IV (Auditable Intelligence).

### Key Entities

- **Merge Request**: A proposed code change in a GitLab repository, containing a diff, title, description, source/target branches, review threads/comments, pipeline run state, and commit history. The primary input to the agent. The agent tracks the full MR lifecycle — any change to these attributes triggers re-analysis.
- **Architecture Decision Log (ADL)**: A single accumulating markdown file (`ARCHITECTURE_DECISION_LOG.md`) with chronological short entries summarizing architecturally significant changes.
- **Architecture Decision Record (ADR)**: An individual markdown file in `adr/` providing detailed context for a particularly impactful change — covers the decision, alternatives, consequences, and affected services.
- **Significance Classification**: The agent's determination of whether a change is non-significant, moderately significant (ADL only), or highly significant (ADL + ADR).
- **Change Scope**: The cross-repo impact footprint of a change, as determined by the scope analysis skill. Includes: related ticket references found in other repos, documented and undocumented service dependencies, shared API contracts, and git blame history (prior MRs that modified the same lines). Feeds into significance classification.
- **Processing State**: A persistent record (`.agent-state.json` in the architecture-decisions repo) tracking each previously analyzed MR: its identifier (project + MR IID), the last-seen state snapshot (latest commit SHA, comment count, description hash, pipeline status), the assigned significance level, and a reference to the corresponding ADL entry position. Used by FR-010/FR-011 to detect changes and locate entries for updates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When run against the 6 sample MRs, the agent correctly identifies at least 80% of architecturally significant vs. non-significant changes (validated by evaluator judgment).
- **SC-002**: Each ADL entry is understandable by a developer unfamiliar with the MRs — they can describe what changed and why after reading only the ADL, without consulting the original diff.
- **SC-003**: The agent produces ADR files for the most impactful changes (at minimum for the PLAT-034 V2 rework MRs) with sufficient detail that a new team member could understand the design decision.
- **SC-004**: The agent can process all 6 sample MRs and commit results to GitLab in a single run without manual intervention.
- **SC-005**: An evaluator can set up the environment (via `setup.sh`), run the agent, and observe results in GitLab within 30 minutes, following only the README.
- **SC-006**: The design document clearly articulates why the chosen approach was selected over alternatives, with at least 2 trade-offs discussed.

## Assumptions

- The agent operates against GitLab (either gitlab.com or a self-hosted instance) with a valid Personal Access Token with `api` scope.
- The sample repositories (order-service, payment-service, architecture-decisions) are set up via the provided `setup.sh` script in a private GitLab group.
- The agent is a working prototype — production concerns like high availability, retry queues, and comprehensive error handling are out of scope.
- An LLM (any provider) will be used for diff analysis and classification, as purely rule-based approaches are insufficient for nuanced architectural significance detection.
- The agent runs on-demand (triggered manually or via CI) rather than as a continuously running service.
- MR review comments (provided in `gitlab-comments.md` and posted by `setup.sh`) are available via the GitLab API and serve as additional context for the agent's analysis.
- The architecture-decisions repository starts with an empty `ARCHITECTURE_DECISION_LOG.md` and an empty `adr/` directory.
- Feature 002 (Architecture Baseline Snapshot) provides an optional pre-step: if no baseline exists, the agent generates one before MR analysis. The baseline enriches ADL/ADR entries with context about what the architecture looked like before the change. Feature 001 operates independently if no baseline exists, but produces richer output when one is available.
- The shared escalation criteria skill and multi-agent review pattern (defined in Feature 002) apply to MR analysis as well. Uncertain classifications are submitted to multi-agent review; escalation precedents from `.agent-state.json` are consulted before human escalation.
- The sample repositories have shallow commit history (2 commits on main each). Git blame (FR-012e) is fully implemented but will provide minimal historical context against sample data. The demo primarily showcases ticket-reference and code-dependency analysis for cross-repo scope; git blame demonstrates its value on mature repos with deeper history.
