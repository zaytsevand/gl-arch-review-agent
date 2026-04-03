# LLM Interface Schemas

**Feature**: 001-adr-review-agent | **Date**: 2026-04-03

These schemas define the structured output format for Anthropic tool_use calls.

## Classification Schema

Used by: All three analysis perspectives (api_contract, dependency_coupling, risk_security)

```json
{
  "name": "classify_architectural_significance",
  "description": "Classify whether an MR diff represents an architecturally significant change",
  "input_schema": {
    "type": "object",
    "properties": {
      "significance": {
        "type": "string",
        "enum": ["non_significant", "moderate", "high"]
      },
      "change_type": {
        "type": "string",
        "enum": ["api_change", "new_dependency", "schema_change", "infrastructure", "security", "config_change", "dead_code", "contract_change"]
      },
      "confidence": {
        "type": "string",
        "enum": ["high", "medium", "borderline"]
      },
      "summary": {
        "type": "string",
        "maxLength": 120
      },
      "rationale": {
        "type": "string"
      },
      "affected_services": {
        "type": "array",
        "items": { "type": "string" }
      },
      "areas_of_impact": {
        "type": "array",
        "items": { "type": "string" }
      },
      "relevant_files": {
        "type": "array",
        "items": { "type": "string" }
      }
    },
    "required": ["significance", "change_type", "confidence", "summary", "rationale", "affected_services"]
  }
}
```

## ADR Generation Schema

Used by: ADR content generation call (after classification)

```json
{
  "name": "generate_adr_content",
  "description": "Generate Architecture Decision Record content for a highly significant change",
  "input_schema": {
    "type": "object",
    "properties": {
      "title": { "type": "string" },
      "context": { "type": "string" },
      "decision": { "type": "string" },
      "alternatives": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": { "type": "string" },
            "reason_rejected": { "type": "string" }
          },
          "required": ["name", "reason_rejected"]
        }
      },
      "consequences": {
        "type": "array",
        "items": { "type": "string" }
      }
    },
    "required": ["title", "context", "decision", "consequences"]
  }
}
```

## Escalation Assessment Schema

Used by: Escalation criteria skill after multi-agent disagreement

```json
{
  "name": "assess_escalation",
  "description": "Evaluate whether a finding requires human escalation",
  "input_schema": {
    "type": "object",
    "properties": {
      "requires_escalation": { "type": "boolean" },
      "criteria_matched": {
        "type": "array",
        "items": {
          "type": "string",
          "enum": ["security_implication", "cross_team_impact", "irreversible_decision", "unresolvable_ambiguity", "agent_disagreement"]
        }
      },
      "human_question": {
        "type": "string",
        "description": "What specific decision the human needs to make"
      },
      "agent_assessments_summary": {
        "type": "string",
        "description": "Summary of what each perspective agent concluded"
      }
    },
    "required": ["requires_escalation", "criteria_matched"]
  }
}
```
