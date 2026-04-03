# CLI Interface Contract

**Feature**: 001-adr-review-agent | **Date**: 2026-04-03

## Entry Point

```
adr-agent <command> [options]
```

## Commands

### `review-mr`

Analyze a single merge request.

```
adr-agent review-mr <MR_URL_OR_ID> [options]
```

| Argument / Option | Required | Default | Description |
|-------------------|----------|---------|-------------|
| `MR_URL_OR_ID` | yes | — | GitLab MR URL or `project_path!iid` |
| `--gitlab-url` | no | `$GITLAB_URL` | GitLab instance URL |
| `--gitlab-token` | no | `$GITLAB_TOKEN` | Personal Access Token |
| `--arch-repo` | yes | — | Path or URL of architecture-decisions repo |
| `--model` | no | `claude-sonnet-4-6` | LLM model for analysis |
| `--dry-run` | no | false | Analyze but don't commit/comment |
| `--verbose` | no | false | Show classification reasoning |

### `review-repo`

Analyze all MRs in a repository.

```
adr-agent review-repo <REPO_PATH_OR_URL> [options]
```

| Argument / Option | Required | Default | Description |
|-------------------|----------|---------|-------------|
| `REPO_PATH_OR_URL` | yes | — | GitLab repo path or URL |
| `--state` | no | `all` | MR state filter: `opened`, `merged`, `all` |
| `--gitlab-url` | no | `$GITLAB_URL` | GitLab instance URL |
| `--gitlab-token` | no | `$GITLAB_TOKEN` | Personal Access Token |
| `--arch-repo` | yes | — | Path or URL of architecture-decisions repo |
| `--model` | no | `claude-sonnet-4-6` | LLM model |
| `--dry-run` | no | false | Analyze but don't commit/comment |

### `review-group`

Analyze all MRs across all repos in a GitLab group.

```
adr-agent review-group <GROUP_PATH> [options]
```

| Argument / Option | Required | Default | Description |
|-------------------|----------|---------|-------------|
| `GROUP_PATH` | yes | — | GitLab group path |
| `--state` | no | `all` | MR state filter |
| `--gitlab-url` | no | `$GITLAB_URL` | GitLab instance URL |
| `--gitlab-token` | no | `$GITLAB_TOKEN` | Personal Access Token |
| `--arch-repo` | yes | — | Architecture-decisions repo |
| `--model` | no | `claude-sonnet-4-6` | LLM model |
| `--dry-run` | no | false | Analyze only |

### `snapshot`

Generate an Architecture Baseline Document (Feature 002).

```
adr-agent snapshot <REPO_PATHS...> [options]
```

| Argument / Option | Required | Default | Description |
|-------------------|----------|---------|-------------|
| `REPO_PATHS` | yes | — | One or more repo paths to scan |
| `--arch-repo` | yes | — | Architecture-decisions repo |
| `--gitlab-url` | no | `$GITLAB_URL` | GitLab instance URL |
| `--gitlab-token` | no | `$GITLAB_TOKEN` | Personal Access Token |
| `--model` | no | `claude-sonnet-4-6` | LLM model |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITLAB_URL` | GitLab instance URL (e.g., `https://gitlab.com`) |
| `GITLAB_TOKEN` | Personal Access Token with `api` scope |
| `ANTHROPIC_API_KEY` | Anthropic API key for LLM calls |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — all MRs processed, results committed |
| 1 | Partial success — some MRs skipped (LLM failure), partial results committed |
| 2 | Authentication failure (GitLab or LLM) |
| 3 | Configuration error (missing required args/env vars) |
| 4 | Escalation pending — items blocked awaiting human review |

## Output

- ADL entries appended to `ARCHITECTURE_DECISION_LOG.md` in the arch repo
- ADR files created in `adr/` directory in the arch repo
- Processing state updated in `.agent-state.json` in the arch repo
- MR comments posted on analyzed MRs (unless `--dry-run`)
- Pipeline status check after commit
- Summary printed to stdout
