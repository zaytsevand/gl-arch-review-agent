# Quickstart: ADR Review Agent

## Prerequisites

- Python 3.11+
- Git
- A GitLab Personal Access Token with `api` scope
- An Anthropic API key

## Setup

```bash
# Clone the agent repo
git clone <agent-repo-url>
cd adr-review-agent

# Install dependencies
pip install -e .

# Set environment variables
export GITLAB_URL="https://gitlab.com"     # or your GitLab instance
export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxx"
```

## Create the Test Environment

```bash
# Clone the test assignment repo
git clone <test-assignment-repo-url>
cd adr-test-agent-unlimit

# Run setup to create GitLab projects, branches, MRs, and review comments
GITLAB_TOKEN="$GITLAB_TOKEN" ./setup.sh
```

This creates:
- `order-service` repo with 3 MRs
- `payment-service` repo with 3 MRs
- `architecture-decisions` repo (empty ADL + empty adr/)

## Run the Agent

### Analyze all MRs in the group (recommended for demo)

```bash
adr-agent review-group unlimit-test-agent \
  --arch-repo unlimit-test-agent/architecture-decisions
```

### Analyze a single repo

```bash
adr-agent review-repo unlimit-test-agent/order-service \
  --arch-repo unlimit-test-agent/architecture-decisions
```

### Analyze a single MR

```bash
adr-agent review-mr "unlimit-test-agent/order-service!3" \
  --arch-repo unlimit-test-agent/architecture-decisions
```

### Generate architecture baseline (snapshot)

```bash
adr-agent snapshot \
  unlimit-test-agent/order-service \
  unlimit-test-agent/payment-service \
  --arch-repo unlimit-test-agent/architecture-decisions
```

### Dry run (analyze without committing or commenting)

```bash
adr-agent review-group unlimit-test-agent \
  --arch-repo unlimit-test-agent/architecture-decisions \
  --dry-run --verbose
```

## Verify Results

After the agent runs, check the architecture-decisions repo:

1. **ADL**: `ARCHITECTURE_DECISION_LOG.md` should have entries for significant MRs
2. **ADRs**: `adr/` directory should have files for high-impact changes
3. **State**: `.agent-state.json` shows which MRs were analyzed
4. **MR Comments**: Check the MRs in order-service and payment-service for agent-posted feedback
5. **Pipeline**: Verify the architecture-decisions CI pipeline is green

## Expected Output

For the 6 sample MRs, expect approximately:
- 1 non-significant MR (ORD-142: logging typos)
- 2 moderate MRs (ORD-158: statistics endpoint, PAY-087: validation extraction)
- 3 highly significant MRs (PLAT-034 x2: V2 workflow, PAY-095: WebSocket)
- 2-3 ADR files (at minimum for PLAT-034 and PAY-095)
- MR comments on significant MRs

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Authentication failed` | Verify `GITLAB_TOKEN` has `api` scope |
| `Model not found` | Verify `ANTHROPIC_API_KEY` is valid |
| `Pipeline failed after commit` | Check markdownlint rules in architecture-decisions repo |
| `MR already processed` | Delete `.agent-state.json` to force re-analysis |
