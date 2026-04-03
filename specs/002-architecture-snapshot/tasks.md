# Tasks: Architecture Baseline Snapshot

**Input**: Design documents from `/specs/002-architecture-snapshot/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md
**Depends on**: Feature 001 (ADR Review Agent) must be implemented first

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: New models and infrastructure for baseline scanning

- [x] T001 Implement Pydantic models for baseline entities in `src/models/baseline.py` — ServiceInventoryEntry, TechStack, APIEndpoint, ConsumedAPI, DataStore, CIConfig, CommunicationLink, BaselineDocument, ExternalRef, FlaggedUnknown per data-model.md
- [x] T002 [P] Create Jinja2 template for baseline document in `src/templates/baseline_document.md.j2` — mandatory sections (services inventory, communication patterns, tech stack, API contracts, data models, dependency graph) + conditional optional sections (security, compliance, data flows, technical debt). Include generation timestamp and repos-scanned header.
- [x] T003 [P] Write baseline synthesis system prompt in `src/prompts/baseline_synthesis.py` — instruct LLM to synthesize structured scan results into a coherent, human-readable narrative. Focus on relationships and significance, not raw listing. Include instructions for flagging uncertain findings.

**Checkpoint**: Baseline models, template, and prompt ready. Scanner implementation can begin.

---

## Phase 2: User Story 1 — Scan Codebase and Produce Baseline (Priority: P1)

**Goal**: Agent scans one or more repos and produces a structured Architecture Baseline Document capturing services, communication, APIs, data models, tech stack, and dependencies.

**Independent Test**: Point agent at sample order-service + payment-service repos, verify baseline accurately reflects their architecture.

### Implementation for User Story 1

- [x] T004 [US1] Implement source file scanner in `src/services/codebase_scanner.py` — given a cloned repo path, walk all source files and extract structured facts using regex heuristics: controller classes + endpoint annotations, client classes + HTTP calls, entity classes + JPA annotations, configuration values from application.yml
- [x] T005 [US1] Implement build file scanner in `src/services/codebase_scanner.py` — extract from build.gradle.kts/pom.xml: language version, framework version, dependencies list, build tool version. Extract from .gitlab-ci.yml: pipeline stages, Docker image, key commands.
- [x] T006 [US1] Implement inter-service communication detector in `src/services/codebase_scanner.py` — identify service-to-service calls by: RestTemplate/WebClient usage with URL patterns, @FeignClient annotations, configuration properties referencing other service URLs/ports, shared DTO class names across repos.
- [x] T007 [US1] Implement external reference extractor in `src/services/codebase_scanner.py` — find Confluence links, Jira ticket references, README URLs in source/config files. Attempt HTTP fetch for web URLs with 5s timeout. Store fetched content or mark as unreachable.
- [x] T008 [US1] Implement multi-repo scan orchestrator in `src/services/codebase_scanner.py` — given a list of repo paths, clone each via GitOps, run all scanners, correlate cross-repo findings (shared DTOs, matching URL references), produce a unified BaselineDocument model.
- [x] T009 [US1] Implement baseline LLM synthesis in `src/services/baseline_writer.py` — send structured scan results (BaselineDocument as JSON) to LLM with baseline_synthesis prompt, receive narrative content for each section, merge into Jinja2 template, write ARCHITECTURE_BASELINE.md to arch repo.
- [x] T010 [US1] Implement uncertain finding handling in `src/services/baseline_writer.py` — for patterns the scanner extracted but couldn't confidently classify, submit to multi-agent review (reuse Feature 001's `src/services/classifier.py` consensus logic). If consensus, include in baseline. If disagreement, add to flagged_unknowns with `pending_review` status.
- [x] T011 [US1] Implement baseline commit workflow in `src/services/baseline_writer.py` — commit ARCHITECTURE_BASELINE.md + updated .agent-state.json to arch repo via GitOps. If flagged unknowns exist, post review comments on the commit listing each pending item.
- [x] T012 [US1] Add `snapshot` CLI command to `src/cli.py` — `adr-agent snapshot <REPO_PATHS...> --arch-repo <path>` per contracts/cli-interface.md. Wire together: clone repos → scan → synthesize → review unknowns → commit → check pipeline.

**Checkpoint**: `adr-agent snapshot` works end-to-end against sample repos. Baseline accurately reflects order-service + payment-service architecture.

---

## Phase 3: User Story 2 — Detect Missing Baseline in Main Workflow (Priority: P2)

**Goal**: When the agent runs review-mr/review-repo/review-group and no valid baseline exists, it auto-generates one before proceeding.

**Independent Test**: Run `adr-agent review-group` against repos with empty architecture-decisions repo, verify baseline is generated first.

### Implementation for User Story 2

- [x] T013 [US2] Implement baseline existence detector in `src/services/baseline_detector.py` — check for `ARCHITECTURE_BASELINE.md` in arch repo by filename AND validate mandatory sections have meaningful content (not empty/placeholder). Return `valid`, `absent`, or `invalid`.
- [x] T014 [US2] Implement baseline content validator in `src/services/baseline_detector.py` — parse the baseline file, check that mandatory sections (services inventory, communication patterns, tech stack) contain at least one substantive entry each. Empty tables or placeholder text = invalid.
- [x] T015 [US2] Integrate baseline detection into review-* commands in `src/cli.py` — before processing MRs, call baseline_detector. If absent/invalid, auto-generate baseline using the snapshot workflow (T012 logic). Log that baseline was auto-generated. Continue to MR analysis.
- [x] T016 [US2] Implement baseline-aware ADL/ADR enrichment in `src/services/adl_writer.py` and `src/services/adr_writer.py` — when baseline exists, include references in generated ADL/ADR content (e.g., "modifies the payment flow described in ARCHITECTURE_BASELINE.md"). Pass baseline context to LLM prompts.

**Checkpoint**: Running `review-group` on repos without a baseline auto-generates one. Subsequent ADL/ADR entries reference the baseline.

---

## Phase 4: User Story 3 — Refresh Baseline After Significant Changes (Priority: P3)

**Goal**: After processing MRs, detect if the baseline is stale and offer a refresh with version preservation.

**Independent Test**: Run agent against MRs that add V2 APIs and new infrastructure, verify it recommends a refresh.

### Implementation for User Story 3

- [x] T017 [US3] Implement staleness detector in `src/services/baseline_detector.py` — after MR batch processing, count high-significance ADL entries since last baseline generation (from state). If >3 high entries OR any `infrastructure`/`new_dependency` change type, flag as stale.
- [x] T018 [US3] Implement baseline versioning in `src/services/baseline_writer.py` — when refreshing, rename existing `ARCHITECTURE_BASELINE.md` to `ARCHITECTURE_BASELINE_v{N}.md` (N = incremented version from state), generate new baseline, commit both files.
- [x] T019 [US3] Extend state manager for baseline tracking in `src/services/state_manager.py` — add fields to ProcessingState: `baseline_generated_at` (datetime), `baseline_version` (int), `baseline_repos_scanned` (list[str]). Update on generation/refresh.
- [x] T020 [US3] Integrate staleness check into review-* commands in `src/cli.py` — after MR processing completes, call staleness detector. If stale, print recommendation and optionally refresh (with `--auto-refresh` flag or interactive prompt).

**Checkpoint**: Agent detects stale baseline after processing significant MRs, preserves old version, generates fresh baseline.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Quality improvements and validation

- [x] T021 [P] Add sample source files to `tests/fixtures/sample_source/` — simplified versions of order-service and payment-service source files for scanner unit testing (controllers, entities, configs, build files)
- [x] T022 [P] Create unit test for codebase scanner in `tests/unit/test_codebase_scanner.py` — test endpoint extraction, entity detection, inter-service call detection, build file parsing against sample fixtures
- [x] T023 [P] Create unit test for baseline detector in `tests/unit/test_baseline_detector.py` — test valid/absent/invalid detection, staleness heuristic
- [x] T024 Run `adr-agent snapshot` against sample repos, manually verify baseline captures at least 90% of discoverable facts (SC-001)
- [x] T025 Verify onboarding readability (SC-002): have a developer unfamiliar with the services read the baseline and describe each service's role and communication patterns

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies beyond Feature 001 being implemented
- **US1 Scan & Produce (Phase 2)**: Depends on Phase 1 (models, template, prompt)
- **US2 Detection (Phase 3)**: Depends on US1 (needs snapshot logic to auto-generate)
- **US3 Refresh (Phase 4)**: Depends on US1 + US2 (needs baseline to refresh)
- **Polish (Phase 5)**: Depends on all user stories

### Parallel Opportunities

**Phase 1**:
```
T001 (models) ─┐
T002 (template) ┤ all parallel
T003 (prompt) ──┘
```

**Phase 2 (US1)**:
```
T004 (source scanner) ──┐
T005 (build scanner) ───┤ parallel scanners
T006 (comm detector) ───┤
T007 (ext refs) ────────┘
         ↓
T008 (orchestrator) → T009 (synthesis) → T010 (unknowns) → T011 (commit) → T012 (CLI)
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Models + template + prompt
2. Complete Phase 2: Scanner + synthesis + CLI
3. **STOP and VALIDATE**: `adr-agent snapshot` produces accurate baseline
4. This alone delivers the core value — architecture documentation from code

### Incremental Delivery

1. Phase 1 → Infrastructure ready
2. US1 → Standalone snapshot works
3. US2 → Auto-detection in main workflow
4. US3 → Staleness + refresh
5. Polish → Testing + validation

---

## Notes

- Feature 002 extends Feature 001 — all new code goes into existing `src/` structure
- No new dependencies needed
- Multi-agent review reuses Feature 001's `classifier.py` consensus logic
- Escalation reuses Feature 001's `escalation.py`
- Total: 25 tasks across 5 phases
