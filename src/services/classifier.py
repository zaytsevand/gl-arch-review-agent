from __future__ import annotations

import asyncio
import logging
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

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS = 2000

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
    re.compile(r".*Controller.*\.java$"),
    re.compile(r".*Resource.*\.java$"),
    re.compile(r".*Client.*\.java$"),
    re.compile(r".*Feign.*\.java$"),
    re.compile(r".*Listener.*\.java$"),
    re.compile(r".*Publisher.*\.java$"),
    re.compile(r".*Consumer.*\.java$"),
    re.compile(r".*Producer.*\.java$"),
    re.compile(r".*Entity.*\.java$"),
    re.compile(r".*Model.*\.java$"),
    re.compile(r".*/model/.*\.java$"),
    re.compile(r".*/dto/.*\.java$"),
    re.compile(r".*/config/.*\.java$"),
    re.compile(r".*/handler/.*\.java$"),
    re.compile(r".*migration.*"),
    re.compile(r".*application.*\.(yml|yaml|properties)$"),
    re.compile(r".*build\.gradle.*$"),
    re.compile(r".*pom\.xml$"),
    re.compile(r".*\.gitlab-ci\.yml$"),
    re.compile(r".*Dockerfile.*$"),
    re.compile(r".*docker-compose.*$"),
]


def filter_relevant_diffs(diffs: list[FileDiff]) -> list[FileDiff]:
    relevant = []
    for d in diffs:
        path = d.new_path or d.old_path
        if any(pattern.match(path) for pattern in ARCH_RELEVANT_PATTERNS):
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
        diff_content = d.diff
        if len(diff_content) > MAX_DIFF_CHARS:
            truncated_chars = len(diff_content) - MAX_DIFF_CHARS
            diff_content = diff_content[:MAX_DIFF_CHARS] + f"\n[... truncated — {truncated_chars} additional chars omitted]"
            logger.warning(
                "Diff for %s truncated: %d chars omitted",
                d.new_path, truncated_chars,
            )
        parts.append(f"```diff\n{diff_content}\n```")

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

    # Weighted confidence: use the confidence of the majority voters,
    # not all voters, so a single BORDERLINE dissenter doesn't drag down
    # a consensus of two HIGH-confidence perspectives.
    majority_perspectives = [
        p for p in perspectives if p.classification.significance == most_common_sig
    ] if consensus else perspectives

    conf_weights = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.BORDERLINE: 1}
    total_weight = sum(
        conf_weights[p.classification.confidence] for p in majority_perspectives
    )
    avg_weight = total_weight / len(majority_perspectives) if majority_perspectives else 2

    if avg_weight >= 2.5:
        agg_confidence = Confidence.HIGH
    elif avg_weight >= 1.5:
        agg_confidence = Confidence.MEDIUM
    else:
        agg_confidence = Confidence.BORDERLINE

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

    # Log specific errors for each failed perspective agent (#7)
    for name_prompt, result in zip(perspectives_config, results):
        if isinstance(result, Exception):
            logger.error(
                "Perspective agent '%s' failed: %s: %s",
                name_prompt[0], type(result).__name__, result,
            )

    if not valid_results:
        error_details = "; ".join(
            f"{name}: {type(r).__name__}"
            for (name, _), r in zip(perspectives_config, results)
            if isinstance(r, Exception)
        )
        return MultiAgentReview(
            escalation_triggered=True,
            escalation_reason=f"All perspective agents failed ({error_details})",
        )

    return aggregate_perspectives(valid_results)
