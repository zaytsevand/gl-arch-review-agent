from __future__ import annotations

import asyncio
import re
from collections import Counter

import anthropic

from src.models.classification import (
    Confidence,
    MultiAgentReview,
    PerspectiveResult,
    Significance,
    SignificanceClassification,
)
from src.models.gitlab_types import FileDiff, MRAnalysisInput
from src.prompts import api_contract, dependency_coupling, risk_security

CLASSIFICATION_TOOL = {
    "name": "classify_architectural_significance",
    "description": "Classify whether an MR diff represents an architecturally significant change",
    "input_schema": {
        "type": "object",
        "properties": {
            "significance": {
                "type": "string",
                "enum": ["non_significant", "moderate", "high"],
            },
            "change_type": {
                "type": "string",
                "enum": [
                    "api_change",
                    "new_dependency",
                    "schema_change",
                    "infrastructure",
                    "security",
                    "config_change",
                    "dead_code",
                    "contract_change",
                ],
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "borderline"],
            },
            "summary": {"type": "string", "maxLength": 120},
            "rationale": {"type": "string"},
            "affected_services": {
                "type": "array",
                "items": {"type": "string"},
            },
            "areas_of_impact": {
                "type": "array",
                "items": {"type": "string"},
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "significance",
            "change_type",
            "confidence",
            "summary",
            "rationale",
            "affected_services",
        ],
    },
}

ARCH_RELEVANT_PATTERNS = [
    r".*Controller.*\.java$",
    r".*Resource.*\.java$",
    r".*Client.*\.java$",
    r".*Feign.*\.java$",
    r".*Listener.*\.java$",
    r".*Publisher.*\.java$",
    r".*Consumer.*\.java$",
    r".*Producer.*\.java$",
    r".*Entity.*\.java$",
    r".*Model.*\.java$",
    r".*/model/.*\.java$",
    r".*/dto/.*\.java$",
    r".*/config/.*\.java$",
    r".*/handler/.*\.java$",
    r".*migration.*",
    r".*application.*\.(yml|yaml|properties)$",
    r".*build\.gradle.*$",
    r".*pom\.xml$",
    r".*\.gitlab-ci\.yml$",
    r".*Dockerfile.*$",
    r".*docker-compose.*$",
]


def filter_relevant_diffs(diffs: list[FileDiff]) -> list[FileDiff]:
    relevant = []
    for d in diffs:
        path = d.new_path or d.old_path
        if any(re.match(pattern, path) for pattern in ARCH_RELEVANT_PATTERNS):
            relevant.append(d)
    return relevant


def build_user_message(mr: MRAnalysisInput, relevant_diffs: list[FileDiff]) -> str:
    parts = [
        f"## MR: {mr.title}",
        f"**Service**: {mr.project_path}",
        f"**Branch**: {mr.source_branch} → {mr.target_branch}",
        f"**State**: {mr.state}",
        f"**Description**: {mr.description or '(none)'}",
        "",
        f"## Files changed ({len(mr.diffs)} total, {len(relevant_diffs)} architecturally relevant):",
    ]

    for d in relevant_diffs:
        parts.append(f"\n### {d.new_path}")
        if d.new_file:
            parts.append("(NEW FILE)")
        elif d.deleted_file:
            parts.append("(DELETED)")
        parts.append(f"```diff\n{d.diff[:2000]}\n```")

    if mr.discussions:
        parts.append("\n## Review Discussions:")
        for disc in mr.discussions:
            status = "RESOLVED" if disc.resolved else "UNRESOLVED"
            loc = f" ({disc.file_path}:{disc.line_number})" if disc.file_path else ""
            parts.append(f"\n### Thread [{status}]{loc}")
            for note in disc.notes:
                if not note.system:
                    parts.append(f"**{note.author}**: {note.body[:500]}")

    if mr.commits:
        parts.append("\n## Commits:")
        for c in mr.commits[:5]:
            parts.append(f"- {c.sha[:7]} {c.title}")

    return "\n".join(parts)


async def classify_perspective(
    client: anthropic.AsyncAnthropic,
    perspective_name: str,
    system_prompt: str,
    user_message: str,
    model: str,
) -> PerspectiveResult:
    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=0,
        system=system_prompt,
        tools=[CLASSIFICATION_TOOL],
        tool_choice={"type": "tool", "name": "classify_architectural_significance"},
        messages=[{"role": "user", "content": user_message}],
    )

    tool_input = {}
    for block in response.content:
        if block.type == "tool_use":
            tool_input = block.input
            break

    classification = SignificanceClassification.model_validate(tool_input)
    return PerspectiveResult(
        perspective=perspective_name, classification=classification
    )


def aggregate_perspectives(perspectives: list[PerspectiveResult]) -> MultiAgentReview:
    sig_votes = Counter(p.classification.significance for p in perspectives)
    most_common_sig, count = sig_votes.most_common(1)[0]

    consensus = count >= 2  # 2/3 agree

    conf_values = [p.classification.confidence for p in perspectives]
    if Confidence.BORDERLINE in conf_values:
        agg_confidence = Confidence.BORDERLINE
    elif Confidence.MEDIUM in conf_values:
        agg_confidence = Confidence.MEDIUM
    else:
        agg_confidence = Confidence.HIGH

    return MultiAgentReview(
        perspectives=perspectives,
        consensus=consensus,
        consensus_significance=most_common_sig if consensus else None,
        consensus_confidence=agg_confidence,
        escalation_triggered=not consensus,
        escalation_reason="Agent disagreement on significance level"
        if not consensus
        else None,
    )


async def classify_mr(
    mr: MRAnalysisInput,
    api_key: str,
    model: str = "claude-sonnet-4-6",
) -> MultiAgentReview:
    relevant_diffs = filter_relevant_diffs(mr.diffs)

    if not relevant_diffs and not mr.diffs:
        return MultiAgentReview(
            consensus=True,
            consensus_significance=Significance.NON_SIGNIFICANT,
            consensus_confidence=Confidence.HIGH,
        )

    if not relevant_diffs:
        relevant_diffs = mr.diffs[:3]

    user_message = build_user_message(mr, relevant_diffs)
    client = anthropic.AsyncAnthropic(api_key=api_key)

    perspectives_config = [
        ("api_contract", api_contract.SYSTEM_PROMPT),
        ("dependency_coupling", dependency_coupling.SYSTEM_PROMPT),
        ("risk_security", risk_security.SYSTEM_PROMPT),
    ]

    tasks = [
        classify_perspective(client, name, prompt, user_message, model)
        for name, prompt in perspectives_config
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_results = [r for r in results if isinstance(r, PerspectiveResult)]

    if not valid_results:
        return MultiAgentReview(
            escalation_triggered=True,
            escalation_reason="All perspective agents failed",
        )

    return aggregate_perspectives(valid_results)
