# CI/CD Variables Contract

**Feature**: 003-gitlab-ci-integration | **Date**: 2026-04-03

## Required Variables

| Variable | Type | Description |
|----------|------|-------------|
| `ADR_AGENT_GITLAB_TOKEN` | string | GitLab Personal Access Token with `api` scope. Must have access to the architecture-decisions repo and all monitored service repos. Configure as masked + protected. |
| `ADR_AGENT_ANTHROPIC_KEY` | string | Anthropic API key for LLM classification. Configure as masked + protected. |
| `ADR_AGENT_ARCH_REPO` | string | GitLab project path of the architecture-decisions repo (e.g., `my-group/architecture-decisions`). |

## Optional Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ADR_AGENT_MODEL` | string | `claude-sonnet-4-6` | Anthropic model for analysis. |
| `ADR_AGENT_DRY_RUN` | boolean | `false` | When `true`, analyze but don't commit or post comments. |
| `ADR_AGENT_TARGET_BRANCHES` | string | (all) | Comma-separated list of target branches to analyze MRs for (e.g., `main,develop`). If unset, all target branches are analyzed. |
| `ADR_AGENT_AUTO_BASELINE` | boolean | `true` | When `true`, auto-generate architecture baseline if missing. |
| `ADR_AGENT_STRICT` | boolean | `false` | When `true`, agent stage blocks MR merge on failure (`allow_failure: false`). |
| `ADR_AGENT_VERBOSE` | boolean | `false` | When `true`, print classification reasoning to pipeline logs. |
| `ADR_AGENT_TIMEOUT` | integer | `600` | Stage timeout in seconds (default: 10 minutes). |

## Variable Scope

- **Project-level**: Set in the service repo's CI/CD settings. Overrides group-level.
- **Group-level**: Set in the GitLab group's CI/CD settings. Applies to all repos in the group.
- **Protected**: Tokens and API keys MUST be configured as protected variables (only available on protected branches/tags and MR pipelines).
- **Masked**: Tokens and API keys MUST be configured as masked variables (hidden in pipeline logs).

## Usage Example

```yaml
# In your service repo's .gitlab-ci.yml:
include:
  - project: 'my-group/adr-review-agent'
    file: 'ci/adr-agent.gitlab-ci.yml'
```

Then set these CI/CD variables in your project or group settings:
- `ADR_AGENT_GITLAB_TOKEN` (masked, protected)
- `ADR_AGENT_ANTHROPIC_KEY` (masked, protected)
- `ADR_AGENT_ARCH_REPO` = `my-group/architecture-decisions`
