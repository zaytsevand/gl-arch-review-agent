# ADR Review Agent

Autonomous agent that identifies architecturally significant changes across GitLab merge requests **and GitHub pull requests**, maintaining an Architecture Decision Log (ADL) and Architecture Decision Records (ADRs).

## Supported Platforms

| Platform | Status | Install extra |
|----------|--------|---------------|
| **GitLab** | ✅ Supported | `pip install 'adr-agent[gitlab]'` |
| **GitHub** | ✅ Supported | `pip install 'adr-agent[github]'` |

## Prerequisites

- Python 3.11+
- Git
- **GitLab**: Personal Access Token with `api` scope
- **GitHub**: Personal Access Token or GitHub App token with `repo` scope
- Anthropic API key

## Setup

### GitLab (default)

```bash
pip install -e '.[gitlab]'
export VCS_PROVIDER="gitlab"          # or omit — gitlab is the default
export VCS_URL="https://gitlab.com"   # optional, defaults to https://gitlab.com
export VCS_TOKEN="glpat-xxxxxxxxxxxx"
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxx"
```

<details>
<summary>Legacy environment variables (still supported)</summary>

```bash
export GITLAB_URL="https://gitlab.com"
export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"
```
</details>

### GitHub

```bash
pip install -e '.[github]'
export VCS_PROVIDER="github"
export VCS_URL="https://github.com"   # optional, defaults to https://github.com
export VCS_TOKEN="ghp_xxxxxxxxxxxx"
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxx"
```

## Usage

### Bootstrap a repo (generates CI config + settings)

```bash
adr-agent init --provider github      # creates .github/workflows/adr-agent.yml
adr-agent init --provider gitlab      # adds include to .gitlab-ci.yml
```

### Analyze all MRs/PRs in a GitLab group or GitHub org

```bash
# GitLab
adr-agent review-group unlimit-test-agent \
  --arch-repo unlimit-test-agent/architecture-decisions

# GitHub
adr-agent review-group my-github-org \
  --vcs-provider github \
  --arch-repo my-github-org/architecture-decisions
```

### Analyze a single repository

```bash
adr-agent review-repo unlimit-test-agent/order-service \
  --arch-repo unlimit-test-agent/architecture-decisions
```

### Analyze a single MR/PR

```bash
# GitLab — uses ! separator
adr-agent review-mr "unlimit-test-agent/order-service!3" \
  --arch-repo unlimit-test-agent/architecture-decisions

# GitHub — uses # separator
adr-agent review-mr "owner/repo#42" \
  --vcs-provider github \
  --arch-repo owner/architecture-decisions
```

### Dry run (analyze without committing)

```bash
adr-agent review-group unlimit-test-agent \
  --arch-repo unlimit-test-agent/architecture-decisions \
  --dry-run --verbose
```

## How It Works

1. **Fetches MR/PR data** from GitLab or GitHub (diffs, review threads, pipeline status, commits)
2. **Filters** files to architecturally relevant ones (controllers, clients, configs, entities)
3. **Classifies** significance using 3 parallel LLM perspectives (API contract, dependency coupling, risk/security)
4. **Aggregates** perspectives — 2/3 consensus required; disagreement triggers escalation
5. **Generates** ADL entries (for moderate + high) and ADR files (for high only)
6. **Commits** results to the architecture-decisions repo
7. **Posts** feedback on the MR/PR with classification summary
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
| `VCS_PROVIDER` | No (default: `gitlab`) | VCS platform: `gitlab` or `github` |
| `VCS_URL` | No | VCS instance URL (defaults to `https://gitlab.com` or `https://github.com`) |
| `VCS_TOKEN` | Yes | Access token for the VCS platform |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `GITLAB_URL` | No | _(deprecated alias for `VCS_URL`)_ |
| `GITLAB_TOKEN` | No | _(deprecated alias for `VCS_TOKEN`)_ |

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

## CI/CD Integration

### GitHub Actions (Quick Start)

Run `adr-agent init --provider github` in your repo, or manually copy `ci/adr-agent.github-actions.yml` to `.github/workflows/adr-agent.yml`.

Then set these repository secrets/variables:

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `ANTHROPIC_API_KEY` | Secret | Yes | Anthropic API key |
| `ADR_ARCH_REPO` | Variable | Yes | Path to architecture-decisions repo |
| `ADR_AGENT_MODEL` | Variable | No | LLM model (default: `claude-sonnet-4-6`) |
| `ADR_AGENT_DRY_RUN` | Variable | No | `true`/`false` (default: `false`) |
| `ADR_AGENT_VERBOSE` | Variable | No | `true`/`false` (default: `false`) |

### GitLab CI (Quick Start — 3 lines)

Add to your service repo's `.gitlab-ci.yml`:

```yaml
include:
  - project: 'your-group/adr-review-agent'
    file: 'ci/adr-agent.gitlab-ci.yml'
```

Then set these CI/CD variables in **Settings > CI/CD > Variables**:

| Variable | Required | Type | Description |
|----------|----------|------|-------------|
| `ADR_AGENT_GITLAB_TOKEN` | Yes | Masked, protected | GitLab PAT with `api` scope |
| `ADR_AGENT_ANTHROPIC_KEY` | Yes | Masked, protected | Anthropic API key |
| `ADR_AGENT_ARCH_REPO` | Yes | String | Path to architecture-decisions repo |
| `ADR_AGENT_MODEL` | No | String | LLM model (default: `claude-sonnet-4-6`) |
| `ADR_AGENT_DRY_RUN` | No | `true`/`false` | Analyze without committing (default: `false`) |
| `ADR_AGENT_TARGET_BRANCHES` | No | String | Comma-separated target branches (default: all) |
| `ADR_AGENT_AUTO_BASELINE` | No | `true`/`false` | Auto-generate baseline if missing (default: `true`) |
| `ADR_AGENT_STRICT` | No | `true`/`false` | Block MR merge on failure (default: `false`) |
| `ADR_AGENT_VERBOSE` | No | `true`/`false` | Print classification reasoning (default: `false`) |

### Group-Level Setup

To apply the agent to **all repos in a GitLab group**:

1. Go to your group's **Settings > CI/CD > General pipelines**
2. Add the CI include in the group's CI/CD configuration:
   ```yaml
   include:
     - project: 'your-group/adr-review-agent'
       file: 'ci/adr-agent.gitlab-ci.yml'
   ```
3. Set the required CI/CD variables at the **group level** (Settings > CI/CD > Variables)
4. All repos in the group will now run the agent on every MR

Repo-level variable overrides take precedence over group-level settings.

### Behavior

- **Advisory by default**: Agent stage uses `allow_failure: true` — it won't block MRs
- **Strict mode**: Set `ADR_AGENT_STRICT=true` to make the agent stage blocking
- **MR-only**: Agent only runs on merge request pipelines, not branch pushes or tags
- **Concurrent safe**: If two agent runs conflict on the architecture-decisions repo, the agent retries with rebase (up to 3 attempts)

### Troubleshooting

| Problem | Solution |
|---------|----------|
| `Missing required CI/CD variables` | Set `ADR_AGENT_GITLAB_TOKEN`, `ADR_AGENT_ANTHROPIC_KEY`, `ADR_AGENT_ARCH_REPO` in CI/CD settings |
| Agent doesn't run on my MR | Check `ADR_AGENT_TARGET_BRANCHES` — if set, your target branch must match |
| Agent runs but doesn't commit | Check if `ADR_AGENT_DRY_RUN` is set to `true` |
| Pipeline times out | Increase `ADR_AGENT_TIMEOUT` (default: 600 seconds) |
| Push conflict on architecture-decisions repo | Agent retries 3 times automatically. If it still fails, re-run the pipeline. |
