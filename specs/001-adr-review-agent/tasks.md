# Tasks: ADR Review Agent

**Input**: Design documents from `/specs/001-adr-review-agent/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Project initialization and basic structure

- [x] T001 Create project structure: `src/`, `src/models/`, `src/services/`, `src/templates/`, `src/prompts/`, `tests/`, `tests/unit/`, `tests/integration/`, `tests/fixtures/`
- [x] T002 Initialize Python project with `pyproject.toml` — dependencies: anthropic, python-gitlab, click, pydantic v2, jinja2, tenacity; dev: pytest, respx
- [x] T003 [P] Create `src/__init__.py` and all package `__init__.py` files
- [x] T004 [P] Create `.gitignore` for Python project (venv, __pycache__, .pytest_cache, dist)

**Checkpoint**: Project skeleton builds and `pip install -e .` succeeds

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

- [x] T005 Implement Pydantic models for GitLab input types in `src/models/gitlab_types.py` — MRAnalysisInput, FileDiff, Discussion, Note, CommitInfo per data-model.md
- [x] T006 [P] Implement Pydantic models for classification types in `src/models/classification.py` — SignificanceClassification, ChangeScope, TicketRef, RelatedMR, BlameEntry, MultiAgentReview, PerspectiveResult per data-model.md
- [x] T007 [P] Implement Pydantic models for output types in `src/models/output.py` — ADLEntry, ADRDocument, Alternative per data-model.md
- [x] T008 [P] Implement Pydantic models for state types in `src/models/state.py` — ProcessingState, MRState, EscalationPrecedent per data-model.md
- [x] T009 Implement GitLab API client in `src/services/gitlab_client.py` — authenticate with PAT, fetch MR data (diffs, discussions, pipeline status, commits), list MRs by repo and group, resolve discussion thread state (resolved/unresolved)
- [x] T010 [P] Implement git operations wrapper in `src/services/git_ops.py` — clone repo, run git blame on file line ranges, stage files, commit with message, push to remote
- [x] T011 [P] Implement state manager in `src/services/state_manager.py` — load/save `.agent-state.json`, detect MR changes (compare commit SHA, description hash, discussion count, pipeline status), track ADL entry numbers
- [x] T012 [P] Create shared test fixtures in `tests/conftest.py` — mock GitLab API responses, sample MR diffs from order-service/payment-service, sample discussions with resolved/unresolved threads

**Checkpoint**: Foundation ready — GitLab data can be fetched, models validate, state persists. User story implementation can begin.

---

## Phase 3: User Story 1 — Analyze MR Diffs and Classify Significance (Priority: P1)

**Goal**: Agent retrieves MR data and classifies architectural significance using multi-perspective LLM analysis with three-tier model (non-significant / moderate / high).

**Independent Test**: Point agent at the 6 sample MRs, verify correct classification of each (ORD-142 as non-significant, PLAT-034 as high, etc.)

### Implementation for User Story 1

- [x] T013 [US1] Write API contract analysis system prompt in `src/prompts/api_contract.py` — focus on endpoint changes, DTO modifications, API versioning. Include change type taxonomy, positive/negative examples, structured JSON output instructions.
- [x] T014 [P] [US1] Write dependency/coupling analysis system prompt in `src/prompts/dependency_coupling.py` — focus on inter-service calls, shared state, transaction boundaries, Feign clients
- [x] T015 [P] [US1] Write risk/security analysis system prompt in `src/prompts/risk_security.py` — focus on security changes, dead code, incomplete integration, CORS, data leakage
- [x] T016 [US1] Implement multi-perspective classifier in `src/services/classifier.py` — send MR data to 3 parallel LLM calls (asyncio.gather) with different system prompts, use Anthropic tool_use with SignificanceClassification schema, aggregate results into MultiAgentReview with consensus logic (2/3 agree = consensus)
- [x] T017 [US1] Implement file relevance filter in `src/services/classifier.py` — pre-filter MR diffs to architecturally relevant files before sending to LLM (controllers, clients, entities, configs, build files, CI files per research.md heuristics)
- [x] T018 [US1] Implement scope analysis skill in `src/services/scope_analyzer.py` — extract ticket references from MR title/description/commits/code, search other repos in group for same ticket, read in-repo dependency docs, analyze code for undocumented dependencies (imported clients, URL references)
- [x] T019 [US1] Implement git blame enrichment in `src/services/scope_analyzer.py` — for architecturally relevant changed files, run git blame on changed line ranges, map commit SHAs to merge commits via `git log --merges --grep="See merge request"`
- [x] T020 [US1] Implement review comment weighting in `src/services/classifier.py` — extract resolved vs unresolved discussions from MR data, weight resolved higher in analysis context, include resolution status in LLM prompt context
- [x] T021 [US1] Implement escalation criteria skill in `src/services/escalation.py` — evaluate multi-agent review results against criteria (security implications, cross-team impact, irreversible decisions, agent disagreement), check precedent records in state file before escalating
- [x] T022 [US1] Implement escalation precedent lookup in `src/services/escalation.py` — match finding pattern hash against stored EscalationPrecedent records, apply human decision if match found, skip escalation

**Checkpoint**: Classification pipeline works end-to-end — given an MR, produces a SignificanceClassification with confidence level. Multi-agent consensus and escalation work.

---

## Phase 4: User Story 2 — Maintain Architecture Decision Log (Priority: P1)

**Goal**: Generate ADL entries for significant MRs and append to `ARCHITECTURE_DECISION_LOG.md` with correct table format, confidence markers, and cross-service linking.

**Independent Test**: Run against sample MRs, verify ADL has entries for significant ones only, with correct table columns and no entries for trivial MRs.

### Implementation for User Story 2

- [x] T023 [US2] Create Jinja2 template for ADL table row in `src/templates/adl_entry.md.j2` — columns: #, Date, Service, Change Type, Confidence, Summary, Rationale, ADR link
- [x] T024 [US2] Implement ADL writer in `src/services/adl_writer.py` — read existing ARCHITECTURE_DECISION_LOG.md, detect existing table format, extend with additional columns if needed (Confidence, Rationale), append new row above the comment marker, handle auto-incrementing entry numbers from state
- [x] T025 [US2] Implement ADL entry updating in `src/services/adl_writer.py` — for re-analyzed MRs (FR-011), locate existing entry by number (from MRState), update in-place rather than duplicating
- [x] T026 [US2] Implement significance promotion handling in `src/services/adl_writer.py` — when a previously non-significant MR becomes significant on re-analysis, create a new ADL entry and update processing state
- [x] T027 [US2] Implement CI config reader in `src/services/adl_writer.py` — read target repo `.gitlab-ci.yml` and `.markdownlint.json` to determine linting rules, adapt markdown output to comply (disabled rules MD013, MD033, MD041 for the sample repo)

**Checkpoint**: ADL entries are generated for significant MRs, appended correctly, format is consistent, existing entries update on re-analysis.

---

## Phase 5: User Story 3 — Create Detailed ADR Files (Priority: P2)

**Goal**: Generate standalone ADR files for highly significant changes with structured content (context, decision, alternatives, consequences). Cross-repo MRs sharing a ticket produce one shared ADR.

**Independent Test**: Run against PLAT-034 and PAY-095 MRs, verify ADR files created in `adr/` with complete content and linked from ADL.

### Implementation for User Story 3

- [x] T028 [US3] Create Jinja2 template for ADR document in `src/templates/adr_document.md.j2` — Nygard format with: title, date, status (Proposed), confidence, services, source MR URLs, context, decision, alternatives considered, consequences
- [x] T029 [US3] Implement ADR writer in `src/services/adr_writer.py` — generate ADR content via LLM call using generate_adr_content tool_use schema, render with Jinja2 template, write to `adr/NNN-title-slug.md`
- [x] T030 [US3] Implement cross-repo ADR consolidation in `src/services/adr_writer.py` — when scope analysis detects multiple MRs sharing a ticket reference across repos, generate one shared ADR covering the cross-service decision, link from both ADL entries (FR-006)
- [x] T031 [US3] Implement dead code / incomplete integration flagging in ADR consequences in `src/services/adr_writer.py` — when classifier detects dead code signal, include it in the ADR consequences section as an architectural risk

**Checkpoint**: ADR files are created for high-impact changes, cross-repo MRs produce shared ADRs, ADL entries link to ADR files.

---

## Phase 6: User Story 4 — Commit Results and Post MR Feedback (Priority: P2)

**Goal**: Commit ADL/ADR/state to GitLab, post feedback comments on MRs, verify pipeline after commit.

**Independent Test**: Run agent, verify commits appear in architecture-decisions repo, MR comments posted, pipeline green.

### Implementation for User Story 4

- [x] T032 [US4] Implement GitLab commit workflow in `src/services/git_ops.py` — stage ADL, ADR files, and `.agent-state.json`, commit with descriptive message referencing source MR(s), push to architecture-decisions repo
- [x] T033 [US4] Implement pipeline status checker in `src/services/pipeline_checker.py` — after committing, poll GitLab pipeline API for the architecture-decisions repo with configurable timeout (default 5 min), report success/failure
- [x] T034 [US4] Create Jinja2 template for MR comments in `src/templates/mr_comment.md.j2` — summary comment (links to ADL/ADR), inline comment (specific line feedback), quality comment (documentation inconsistencies)
- [x] T035 [US4] Implement MR comment strategy in `src/services/mr_commenter.py` — for significant MRs: choose between inline, summary, or both based on impact locality. For trivial MRs: no comment. For borderline non-significant: optional brief note. For doc inconsistencies (e.g., wrong build tool in README): low-severity inline comment
- [x] T036 [US4] Implement escalation comment posting in `src/services/mr_commenter.py` — when escalation triggers, post structured comment on MR with: finding, escalation reason, agent assessments, question for human. Mark as blocking

**Checkpoint**: Full output pipeline works — ADL/ADR committed, state updated, MR comments posted, pipeline verified.

---

## Phase 7: User Story 5 — Runnable Demo Against Sample MRs (Priority: P3)

**Goal**: CLI entry point that processes all 6 sample MRs end-to-end with review-group command.

**Independent Test**: Run `setup.sh` → run `adr-agent review-group` → verify ADL, ADRs, MR comments, pipeline.

### Implementation for User Story 5

- [x] T037 [US5] Implement Click CLI entry point in `src/cli.py` — `review-mr`, `review-repo`, `review-group` subcommands with options per cli-interface.md contract. Environment variable fallback for GITLAB_URL, GITLAB_TOKEN, ANTHROPIC_API_KEY
- [x] T038 [US5] Implement review-mr orchestration in `src/cli.py` — wire together: fetch MR data → check state for changes → run scope analysis → run multi-agent classification → check escalation → generate ADL/ADR → commit → post comments → check pipeline
- [x] T039 [US5] Implement review-repo orchestration in `src/cli.py` — list MRs in repo (filtered by state), iterate through each calling review-mr logic, handle partial failures (skip failed MR, continue)
- [x] T040 [US5] Implement review-group orchestration in `src/cli.py` — list repos in group, iterate through each calling review-repo logic
- [x] T041 [US5] Implement `--dry-run` mode in `src/cli.py` — analyze and classify but skip commit and MR comment posting, print results to stdout
- [x] T042 [US5] Implement `--verbose` mode in `src/cli.py` — expose classification reasoning, multi-agent perspectives, scope analysis findings, escalation decisions (Constitution IV: Auditable Intelligence)
- [x] T043 [US5] Create README.md at project root — setup instructions, prerequisites, environment variables, usage examples per quickstart.md, expected output, troubleshooting
- [x] T044 [US5] Create DESIGN.md at project root — approach, architectural decisions, prompt design rationale with actual prompts, alternatives considered, at least 2 trade-offs discussed (FR-019, Constitution VI)

**Checkpoint**: Full demo works end-to-end. `adr-agent review-group` processes 6 MRs, produces ADL + ADRs + MR comments. Evaluator can reproduce from README.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality improvements across all stories

- [x] T045 [P] Add progress bar to CLI for batch MR processing in `src/cli.py`
- [x] T046 [P] Add retry logic with tenacity to LLM calls in `src/services/classifier.py` and `src/services/adr_writer.py`
- [x] T047 [P] Record sample GitLab API responses and MR diffs in `tests/fixtures/` for offline testing
- [x] T048 Run agent against all 6 sample MRs, manually review ADL/ADR output quality against Constitution III
- [x] T049 Validate classification accuracy: verify at least 5 of 6 MRs classified correctly (SC-001, Constitution Quality Gate)
- [x] T050 Run quickstart.md validation: fresh clone → README setup → working results within 30 minutes (SC-005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 Classification (Phase 3)**: Depends on Foundational — core intelligence
- **US2 ADL (Phase 4)**: Depends on Foundational + US1 (needs classification output)
- **US3 ADR (Phase 5)**: Depends on US2 (needs ADL entry to link from)
- **US4 Commit/Comment (Phase 6)**: Depends on US2 + US3 (needs content to commit)
- **US5 Demo/CLI (Phase 7)**: Depends on US1 + US2 + US3 + US4 (wires everything together)
- **Polish (Phase 8)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (Classification)**: Core — all other stories depend on its output
- **US2 (ADL)**: Depends on US1 classification results
- **US3 (ADR)**: Depends on US2 (ADL entry to link from) + US1 (classification)
- **US4 (Commit/Comment)**: Depends on US2 + US3 output
- **US5 (Demo/CLI)**: Integrates all stories

### Within Each User Story

- Prompts/templates before services that use them
- Models before services (already in Foundational)
- Core service before integration points
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 2 (Foundational)**:
```
T005 (gitlab models) → T009 (gitlab client)
T006 (classification models) ─┐
T007 (output models) ─────────┤ all parallel, then T009-T012
T008 (state models) ──────────┘
T010 (git ops) ── parallel with T009
T011 (state manager) ── parallel with T009
T012 (fixtures) ── parallel with T009
```

**Phase 3 (US1 — Classification)**:
```
T013 (api prompt) → T016 (classifier)
T014 (dep prompt) ─┤ all parallel
T015 (risk prompt)─┘
T017 (file filter) ── parallel with T013-T015
T018 (scope analyzer) ── parallel with T016
T019 (git blame) ── after T018
T020 (review comments) ── parallel with T016
T021 (escalation) ── after T016
T022 (precedent lookup) ── after T021
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (Classification)
4. Complete Phase 4: US2 (ADL)
5. **STOP and VALIDATE**: Classification works, ADL entries are generated
6. This alone demonstrates the core value proposition

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → Classification works (MVP core)
3. US2 → ADL entries generated (MVP output)
4. US3 → ADR files for high-impact changes
5. US4 → Commits + MR comments (GitLab integration complete)
6. US5 → Full CLI + demo + docs (evaluation-ready)
7. Polish → Quality validation

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps to user stories from spec.md
- Each user story builds on prior stories (US1→US2→US3→US4→US5)
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
- Total: 50 tasks across 8 phases
