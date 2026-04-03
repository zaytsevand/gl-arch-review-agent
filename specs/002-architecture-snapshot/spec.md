# Feature Specification: Architecture Baseline Snapshot

**Feature Branch**: `002-architecture-snapshot`  
**Created**: 2026-04-03  
**Status**: Draft  
**Input**: User description: "should we add a feature to create a snapshot of current architecture if it is not yet present in a project"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent Scans Codebase and Produces Architecture Baseline (Priority: P1)

When pointed at one or more repositories that lack architecture documentation, the agent scans the codebase and produces an Architecture Baseline Document. This document captures the current state of the system: services and their responsibilities, inter-service communication patterns, API contracts (endpoints, protocols), data models and storage, external dependencies, tech stack, and known architectural patterns (e.g., state machines, event-driven flows). The baseline is committed to the architecture-decisions repository as the foundational reference point for all future ADL/ADR entries.

**Why this priority**: Without a baseline, ADL entries describe changes relative to an unknown starting point. The baseline makes all subsequent architectural documentation meaningful — a reader can understand not just what changed, but what it changed from.

**Independent Test**: Can be tested by pointing the agent at the sample order-service and payment-service repos and verifying it produces a baseline document that accurately reflects the services' architecture (REST endpoints, inter-service calls, data models, tech stack).

**Acceptance Scenarios**:

1. **Given** a set of repositories with no existing architecture documentation, **When** the agent runs in snapshot mode, **Then** it produces a structured Architecture Baseline Document that covers: services inventory, communication patterns, API contracts, data models, tech stack, and dependency graph.
2. **Given** a repository with Spring Boot services communicating via REST, **When** the agent scans the codebase, **Then** it identifies the REST endpoints, inter-service HTTP calls, JPA entities, and application configuration — without relying on external documentation.
3. **Given** a multi-repo setup (e.g., order-service + payment-service), **When** the agent scans both, **Then** the baseline document captures the cross-service relationship (order-service calls payment-service) and maps the shared contracts (PaymentRequest/PaymentResponse DTOs).
4. **Given** a codebase with configuration files (application.yml, build.gradle.kts, .gitlab-ci.yml), **When** the agent scans them, **Then** the baseline includes: service ports, database configuration, CI/CD pipeline structure, and dependency versions.
5. **Given** a codebase containing patterns the agent cannot confidently identify, **When** the agent produces the baseline, **Then** it submits the uncertain findings to multi-agent parallel review. If agents reach consensus, the finding is included autonomously. If agents disagree or the finding matches escalation criteria, the agent raises a review comment with the agents' assessments, blocks finalization of that item, and waits for a human to resolve it.
6. **Given** a finding that is significant but clearly classifiable (agents agree with high confidence, no escalation criteria matched), **When** multi-agent review completes, **Then** the agent finalizes the decision autonomously without human intervention.

---

### User Story 2 - Agent Detects Missing Baseline and Recommends Snapshot (Priority: P2)

When the agent runs its normal ADR review workflow (Feature 001) and encounters a project with no Architecture Baseline Document in the architecture-decisions repository, it detects this gap and recommends running a snapshot before proceeding. This ensures the agent's ADL/ADR output has context.

**Why this priority**: This integrates the snapshot capability into the main workflow. Without it, the user must remember to run the snapshot manually — an automation gap that undermines the agent's autonomous design.

**Independent Test**: Can be tested by running the main agent against repos with an empty architecture-decisions repository and verifying it prompts for / auto-generates a baseline.

**Acceptance Scenarios**:

1. **Given** the architecture-decisions repo has no Architecture Baseline Document, **When** the agent starts processing MRs, **Then** it detects the absence and either auto-generates a baseline or prompts the user to approve generation before continuing.
2. **Given** the architecture-decisions repo already has a valid baseline, **When** the agent starts processing MRs, **Then** it skips baseline generation and proceeds directly to MR analysis.
3. **Given** the agent auto-generates a baseline, **When** it then analyzes MRs, **Then** the ADL/ADR entries reference the baseline where relevant (e.g., "changes the payment flow described in the baseline").

---

### User Story 3 - Agent Refreshes Baseline After Significant Changes (Priority: P3)

After the agent processes a batch of MRs that result in substantial architectural evolution (e.g., new services, new communication patterns, API versioning), it determines whether the existing baseline is stale and offers to produce an updated version. The previous baseline is preserved for historical reference.

**Why this priority**: Architecture baselines drift over time. An auto-refresh mechanism keeps the baseline useful as a living reference, but it's a quality-of-life improvement over the core snapshot and detection capabilities.

**Independent Test**: Can be tested by running the agent against MRs that add significant architecture (e.g., PLAT-034 V2 workflow) and verifying it flags the baseline as potentially stale and offers a refresh.

**Acceptance Scenarios**:

1. **Given** an existing baseline and a batch of highly significant MR analyses, **When** the agent completes processing, **Then** it evaluates whether the cumulative changes warrant a baseline refresh and recommends one if so.
2. **Given** the agent refreshes the baseline, **When** it commits the update, **Then** the previous baseline version is preserved (e.g., as `ARCHITECTURE_BASELINE_v1.md`) and the new version reflects the current state.
3. **Given** a batch of only moderate or non-significant changes, **When** the agent completes processing, **Then** it does not recommend a baseline refresh.

---

### Edge Cases

- What happens when the codebase uses languages or frameworks the agent doesn't recognize?
- How does the agent handle monorepo structures vs. multi-repo setups?
- What if the codebase has architecture documentation in a non-standard format (e.g., Confluence links, inline comments, ADRs in a different repo)?
- How does the agent handle private dependencies or internal libraries it cannot inspect?
- What happens when services communicate through infrastructure not visible in the code (e.g., message queues configured externally, service mesh)?

## Clarifications

### Session 2026-04-03

- Q: How deep should the agent's codebase scan go? → A: Deep + external. The agent scans all source files, build files, configs, and CI/CD definitions, plus follows external references found in the code (Confluence links, README URLs, linked Jira tickets) to enrich the baseline with context not available in the code alone.
- Q: Should the baseline have a prescribed structure or agent-decided format? → A: Prescribed template with flexible sections. Mandatory sections (services inventory, communication patterns, tech stack) are always present. Optional sections (security, compliance, data flows) are added only when the scan finds relevant evidence.
- Q: How does the agent detect that no baseline exists? → A: Check for the baseline filename AND validate that mandatory sections contain meaningful content. Empty files, placeholder-only files, or files missing mandatory sections are treated as absent.
- Q: What should the agent do when it encounters unrecognized patterns? → A: A separate "escalation criteria" skill evaluates whether a finding requires human input. Not all significant decisions need escalation. Before escalating, architectural decisions are evaluated by multiple agents in parallel (multi-agent review). Escalation is triggered by: agent disagreement, low consensus confidence, or findings that match escalation criteria (e.g., security implications, cross-team impact, irreversible decisions). The escalation skill applies across both baseline generation and MR analysis workflows.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Agent MUST perform a deep scan of one or more repositories — all source files, build files, configs, and CI/CD definitions — and produce a structured Architecture Baseline Document capturing: services inventory, communication patterns, API contracts, data models, tech stack, external dependencies, and CI/CD configuration. The agent MUST also follow external references found in the codebase (Confluence links, README URLs, linked Jira tickets) to enrich the baseline with context not available in the code alone.
- **FR-002**: Agent MUST identify inter-service communication by analyzing code-level evidence: HTTP client calls, shared DTOs/contracts, configuration references to other services (URLs, ports, hostnames).
- **FR-003**: Agent MUST extract API contract information from the codebase: REST endpoints (controller annotations, route definitions), request/response DTOs, and documented protocols.
- **FR-004**: Agent MUST identify data models and storage: entity definitions, database configuration, schema management approach (migrations, auto-DDL).
- **FR-005**: Agent MUST extract tech stack information from build files and configuration: language version, framework versions, key dependencies, build tool.
- **FR-006**: Agent MUST commit the Architecture Baseline Document to the architecture-decisions repository alongside the ADL and ADR files.
- **FR-007**: When running the main ADR review workflow, the agent MUST check for the baseline document by filename (e.g., `ARCHITECTURE_BASELINE.md`) AND validate that its mandatory sections contain meaningful content. Empty files, placeholder-only files, or files missing mandatory sections MUST be treated as absent. If absent, the agent MUST generate a baseline before proceeding with MR analysis.
- **FR-008**: Agent MUST be invocable in standalone snapshot mode (independent of MR analysis) via a CLI command that targets specific repos.
- **FR-009**: Agent MUST produce a baseline that is readable by a developer unfamiliar with the codebase — it serves as onboarding documentation, not just a machine-readable inventory. The baseline MUST follow a prescribed template with mandatory sections (services inventory, communication patterns, tech stack, API contracts, data models, dependency graph) and optional sections (security posture, compliance constraints, data flows, known technical debt) included only when the scan finds relevant evidence. Empty boilerplate sections MUST NOT be included.
- **FR-010**: When the baseline is refreshed, the agent MUST preserve the previous version and commit both the archived old version and the new baseline.
- **FR-011**: The baseline document MUST include a generation timestamp and a list of repositories/branches scanned, so readers know what state the snapshot reflects.
- **FR-012**: The agent MUST include a separate escalation criteria skill that evaluates whether a finding requires human input. This skill applies across both baseline generation and MR analysis (Feature 001). Not all significant or uncertain findings require escalation — the skill MUST define explicit criteria for when human involvement is needed (e.g., security implications, cross-team impact, irreversible architectural decisions, unresolvable ambiguity).
- **FR-013**: Before escalating to a human, architectural decisions and uncertain findings MUST be evaluated by multiple agents in parallel (multi-agent review). Each agent independently assesses the finding. Escalation is triggered when: agents disagree on classification, consensus confidence is below a threshold, or the finding matches escalation criteria regardless of confidence. **Complexity justification (Constitution II)**: Multi-agent review reduces false escalations, which directly serves the evaluator's "agent design" criterion — the agent makes better autonomous decisions by cross-checking its own reasoning. In the prototype, "multiple agents" means multiple LLM calls with different analysis perspectives (e.g., security-focused, API-contract-focused, data-model-focused), not separate infrastructure.
- **FR-014**: When multi-agent review reaches consensus (agents agree with sufficient confidence and no escalation criteria are matched), the decision is finalized autonomously without human intervention.
- **FR-015**: When escalation is triggered, the agent MUST raise the concern as a review comment on the relevant MR or baseline commit, clearly stating: what was found, why it was escalated (which criterion triggered), the agents' assessments, and what decision the human needs to make. The item is blocked until a human resolves it.
- **FR-016**: The agent MUST incorporate human feedback from resolved escalations into its future decision-making. For the prototype, this means: resolved escalation decisions are stored in the processing state file (`.agent-state.json`) as precedent records. On subsequent runs, the escalation criteria skill consults these precedents before escalating similar findings — if a human previously resolved an equivalent pattern, the agent applies that decision autonomously. This is a lookup mechanism, not machine learning.

### Key Entities

- **Architecture Baseline Document**: A structured markdown file (e.g., `ARCHITECTURE_BASELINE.md` in the architecture-decisions repo) capturing the current architectural state of the system. Includes: services inventory, communication map, API contracts, data models, tech stack, and dependency graph. Serves as the reference point for ADL/ADR entries.
- **Service Inventory Entry**: A record for each service/repository scanned, including: service name, responsibility, tech stack, exposed APIs, consumed APIs, data stores, and CI/CD configuration.
- **Communication Map**: A description of how services interact — which service calls which, via what protocol, using what contracts. Derived from code analysis, not external documentation.
- **Escalation Criteria Skill**: A separate decision-making module that evaluates whether a finding requires human input. Defines explicit trigger conditions: security implications, cross-team impact, irreversible decisions, unresolvable ambiguity, agent disagreement. Applies across both baseline generation and MR analysis workflows. Learns from resolved escalations to reduce unnecessary future escalations.
- **Multi-Agent Review**: A parallel evaluation pattern where multiple agents independently assess an architectural finding. Consensus (agreement + sufficient confidence) allows autonomous finalization. Disagreement or low confidence triggers the escalation criteria skill for potential human escalation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When run against the sample order-service and payment-service repos, the baseline accurately captures at least 90% of discoverable architectural facts (endpoints, inter-service calls, entities, tech stack) as verified by manual review.
- **SC-002**: A developer unfamiliar with the sample services can read the baseline and correctly describe: what each service does, how they communicate, and what data they manage — without reading the source code.
- **SC-003**: The baseline is generated in a single agent run. Items requiring human escalation are flagged but do not block generation of the remaining baseline content — the baseline is committed with flagged sections marked as pending review, and finalized after human resolution.
- **SC-004**: When the main agent detects a missing baseline, it auto-generates one. Subsequent ADL/ADR entries reference the baseline when describing changes to documented architectural patterns (e.g., "modifies the payment flow described in ARCHITECTURE_BASELINE.md").
- **SC-005**: Baseline refresh preserves the previous version and the new version reflects changes introduced by recently analyzed MRs.

## Assumptions

- The agent primarily infers architecture from code-level artifacts (source files, build configs, CI configs), supplemented by external references found in the codebase (Confluence links, README URLs, Jira tickets). Runtime observability is not required.
- The sample repos (order-service, payment-service) represent a typical Spring Boot microservices setup and serve as the primary test case.
- The Architecture Baseline Document lives in the same architecture-decisions repository as the ADL and ADR files.
- The baseline is a point-in-time snapshot, not a continuously maintained live document — it's refreshed explicitly.
- The agent uses an LLM to synthesize the scanned code artifacts into a coherent, human-readable baseline (raw code scanning alone produces an inventory, not a narrative).
- This feature integrates with Feature 001 (ADR Review Agent) — the baseline is consumed by the MR analysis workflow to provide context for significance classification.
- **Evaluation alignment**: Feature 002 serves the "agent design" criterion (autonomous baseline generation demonstrates sophisticated codebase understanding), "output quality" criterion (baseline enriches all subsequent ADL/ADR entries), and "problem decomposition" criterion (identifying that a baseline is needed before changes can be documented). Feature 001 remains the primary deliverable; Feature 002 is enhancement scope.
