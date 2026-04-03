<!--
  Sync Impact Report
  ==================
  Version change: 0.0.0 → 1.0.0 (initial ratification)
  Modified principles: N/A (initial)
  Added sections:
    - Core Principles (6 principles)
    - Evaluation Alignment
    - Development Workflow
    - Governance
  Removed sections: N/A
  Templates requiring updates:
    - .specify/templates/plan-template.md — ✅ no update needed
      (Constitution Check section already present as dynamic gate)
    - .specify/templates/spec-template.md — ✅ no update needed
      (mandatory sections align with principles)
    - .specify/templates/tasks-template.md — ✅ no update needed
      (phase structure compatible with prototype discipline)
  Follow-up TODOs: none
-->

# ADR Review Agent Constitution

## Core Principles

### I. Signal Over Noise (NON-NEGOTIABLE)

Classification accuracy is the foundation of the agent's value.
The agent MUST correctly distinguish architecturally significant
changes from trivial ones.

- False positives (noise) erode trust in the ADL and waste reader
  attention. The agent MUST NOT generate entries for cosmetic,
  naming-only, or comment-only changes.
- False negatives (missed significant changes) defeat the purpose.
  The agent MUST detect: new API surfaces, new communication
  patterns, cross-service contract changes, data model changes,
  build system migrations, security-relevant changes, and dead
  code or incomplete integration paths (architectural violations
  that indicate unfinished or abandoned patterns).
- When significance is ambiguous, the agent MUST err toward
  inclusion with a lower-confidence marker rather than silent
  omission. Missing a real architectural change is worse than
  including a borderline one.

### II. Prototype Discipline

This is a working prototype, not production software. Every
feature MUST be demonstrable and functional end-to-end.

- No stubs, no mocks-as-features, no "TODO: implement later"
  on the demo path. If it's in the demo, it works.
- No production hardening that distracts from core logic: no HA,
  no retry queues, no monitoring dashboards, no multi-tenant
  support.
- Complexity MUST be justified. If a simpler approach produces
  equivalent output quality, choose the simpler approach.
- The prototype MUST be honest about its limitations in the
  design document rather than hiding them behind incomplete
  abstractions.

### III. Documentation as Product

The ADL and ADR files are the product. The agent code is the
means; the generated documentation is what delivers value.

- Every ADL entry MUST be self-contained: a developer who never
  saw the MR MUST be able to understand what changed and why
  from the entry alone.
- ADR files MUST provide sufficient context for a new team
  member to understand the design decision, including
  alternatives considered and consequences.
- Output format and structure MUST be consistent across entries.
  Readers build expectations from pattern; inconsistency breaks
  comprehension.
- The agent MUST NOT generate boilerplate or filler text. Every
  sentence in the output MUST carry information.

### IV. Auditable Intelligence

When the agent uses an LLM for classification or content
generation, the reasoning MUST be traceable.

- The agent MUST make it possible to understand why a given MR
  was classified at a given significance level. This can be via
  logs, a verbose mode, or structured output — but it MUST exist.
- Prompt design MUST be intentional and documented. The prompts
  are part of the agent's architecture, not throwaway strings.
- The agent MUST incorporate MR review comments as supplementary
  context, not rely solely on the raw diff. Review threads often
  contain the architectural rationale that the diff alone lacks.

### V. GitLab-Native Integration

All inputs come from GitLab. All outputs go to GitLab. The agent
operates within the GitLab ecosystem without requiring manual
data preparation or post-processing.

- The agent MUST read MR data (diffs, metadata, descriptions,
  review comments) via the GitLab API or git operations.
- The agent MUST commit generated ADL/ADR content back to the
  architecture-decisions repository with meaningful commit
  messages that reference the source MR.
- The agent MUST handle multiple repositories in a single run
  (at minimum: order-service and payment-service).
- Authentication MUST use a standard GitLab Personal Access
  Token with `api` scope. No custom auth flows.

### VI. Reproducibility

The full pipeline MUST be reproducible from scratch by a
reviewer following only the README.

- Environment setup via `setup.sh` MUST create all necessary
  GitLab infrastructure (repos, branches, MRs, review comments).
- The agent MUST run against the sample environment and produce
  complete results without manual intervention.
- The README MUST document all prerequisites, configuration,
  and execution steps. No tribal knowledge.
- The design document MUST articulate the chosen approach,
  alternatives considered, and trade-offs. At least two
  non-trivial trade-offs MUST be discussed.

## Evaluation Alignment

The agent is being evaluated against five criteria. All
implementation decisions MUST be traceable to at least one:

| Criterion | What It Measures | Constitution Mapping |
|-----------|-----------------|---------------------|
| Problem decomposition | Breaking ambiguous requirements into concrete engineering decisions | Principle II (Prototype Discipline), design document |
| Agent design | Sensible autonomous decision-making | Principle I (Signal Over Noise), Principle IV (Auditable Intelligence) |
| Signal vs noise | Distinguishing significant from trivial changes | Principle I (Signal Over Noise) — the primary gate |
| Output quality | Useful, well-structured documentation | Principle III (Documentation as Product) |
| Reasoning clarity | Clear communication of approach and trade-offs | Principle VI (Reproducibility), design document |

Implementation choices that do not serve at least one criterion
MUST be questioned. If a feature or abstraction cannot be mapped
to a criterion, it is likely out of scope for the prototype.

## Development Workflow

### Definition of Done

A user story is complete when:

1. The feature works end-to-end against the sample GitLab
   environment (not just unit tests in isolation).
2. Generated ADL/ADR output has been manually reviewed for
   quality against Principle III.
3. The agent's classification decisions are explainable per
   Principle IV.

### Commit Practices

- Each commit MUST represent a coherent, working increment.
- Commit messages MUST reference the user story or functional
  requirement being addressed.
- The design document MUST be updated alongside code changes
  when architectural decisions are made.

### Quality Gates

- Before any PR/MR: run the agent against all 6 sample MRs and
  verify output quality.
- Classification accuracy gate: the agent MUST correctly handle
  at least 5 of 6 sample MRs (per SC-001: 80% threshold).
- README gate: a fresh clone and README-only setup MUST produce
  working results within 30 minutes.

## Governance

This constitution defines the non-negotiable principles for the
ADR Review Agent project. All implementation decisions, code
reviews, and design trade-offs MUST be evaluated against these
principles.

- **Amendments** require updating this file, incrementing the
  version, and verifying consistency with dependent templates
  (spec-template.md, plan-template.md, tasks-template.md).
- **Versioning** follows semantic versioning: MAJOR for principle
  removals or redefinitions, MINOR for new principles or material
  expansions, PATCH for clarifications and wording fixes.
- **Compliance** is verified at two gates: plan creation
  (Constitution Check in plan-template.md) and story completion
  (Definition of Done above).

**Version**: 1.0.0 | **Ratified**: 2026-04-03 | **Last Amended**: 2026-04-03
