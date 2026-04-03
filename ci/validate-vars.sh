#!/bin/sh
# =============================================================================
# ADR Agent — CI Variable Validation
# =============================================================================
# Called by the CI template's before_script to validate required variables.
# Exits 1 with a descriptive error if any required variable is missing.
# =============================================================================

set -e

MISSING=""
COUNT=0

check_var() {
  VAR_NAME="$1"
  DESCRIPTION="$2"
  eval VALUE="\$$VAR_NAME"
  if [ -z "$VALUE" ]; then
    MISSING="$MISSING\n  - $VAR_NAME ($DESCRIPTION)"
    COUNT=$((COUNT + 1))
  fi
}

check_var "ADR_AGENT_GITLAB_TOKEN" "GitLab Personal Access Token with api scope"
check_var "ADR_AGENT_ANTHROPIC_KEY" "Anthropic API key for LLM classification"
check_var "ADR_AGENT_ARCH_REPO"     "GitLab project path of architecture-decisions repo"

if [ $COUNT -gt 0 ]; then
  echo ""
  echo "================================================================"
  echo "  ADR Review Agent — Configuration Error"
  echo "================================================================"
  echo ""
  echo "  Missing $COUNT required CI/CD variable(s):"
  echo -e "$MISSING"
  echo ""
  echo "  Set these in your project or group CI/CD settings:"
  echo "    Settings → CI/CD → Variables"
  echo ""
  echo "  Important: Configure tokens as masked + protected variables."
  echo ""
  echo "  Documentation: See the ADR Review Agent README for setup guide."
  echo "================================================================"
  echo ""
  exit 1
fi

echo "All required CI/CD variables are configured."
