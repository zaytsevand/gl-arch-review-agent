# ADR Review Agent

Autonomous agent that identifies architecturally significant changes across GitLab merge requests and maintains an Architecture Decision Log (ADL) and Architecture Decision Records (ADRs).

## Prerequisites

- Python 3.11+
- Git
- GitLab Personal Access Token with `api` scope
- Anthropic API key

## Setup

```bash
pip install -e .
export GITLAB_URL="https://gitlab.com"
export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxx"
```

## Usage

### Analyze all MRs in a GitLab group

```bash
adr-agent review-group unlimit-test-agent \
  --arch-repo unlimit-test-agent/architecture-decisions
```

### Analyze a single repository

```bash
adr-agent review-repo unlimit-test-agent/order-service \
  --arch-repo unlimit-test-agent/architecture-decisions
```

### Analyze a single MR

```bash
adr-agent review-mr "unlimit-test-agent/order-service!3" \
  --arch-repo unlimit-test-agent/architecture-decisions
```

### Dry run (analyze without committing)

```bash
adr-agent review-group unlimit-test-agent \
  --arch-repo unlimit-test-agent/architecture-decisions \
  --dry-run --verbose
```

## How It Works

1. **Fetches MR data** from GitLab (diffs, review threads, pipeline status, commits)
2. **Filters** files to architecturally relevant ones (controllers, clients, configs, entities)
3. **Classifies** significance using 3 parallel LLM perspectives (API contract, dependency coupling, risk/security)
4. **Aggregates** perspectives — 2/3 consensus required; disagreement triggers escalation
5. **Generates** ADL entries (for moderate + high) and ADR files (for high only)
6. **Commits** results to the architecture-decisions repo
7. **Posts** feedback on the MR with classification summary
8. **Verifies** the CI pipeline after committing

## Classification Levels

| Level | Output | Criteria |
|-------|--------|----------|
| Non-significant | Nothing | Cosmetic changes, typo fixes, variable renames |
| Moderate | ADL entry | New endpoints, internal refactoring with design pattern implications |
| High | ADL entry + ADR | API versioning, cross-service contracts, new infrastructure, state machines |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITLAB_URL` | No (default: `https://gitlab.com`) | GitLab instance URL |
| `GITLAB_TOKEN` | Yes | Personal Access Token with `api` scope |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |

## Demo Setup

```bash
# Clone the test assignment repo and run setup
cd adr-test-agent-unlimit
GITLAB_TOKEN="$GITLAB_TOKEN" ./setup.sh

# Run the agent against all 6 sample MRs
adr-agent review-group unlimit-test-agent \
  --arch-repo unlimit-test-agent/architecture-decisions
```

Expected output: ~4 ADL entries, 2-3 ADR files, MR comments on significant MRs.
