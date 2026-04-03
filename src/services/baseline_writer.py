from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import anthropic
from jinja2 import Environment, FileSystemLoader
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models.baseline import BaselineDocument, FlaggedUnknown
from src.prompts.baseline_synthesis import SYNTHESIS_TOOL, SYSTEM_PROMPT
from src.services.escalation import evaluate_escalation, format_escalation_comment
from src.models.classification import (
    Confidence,
    MultiAgentReview,
    PerspectiveResult,
    Significance,
    SignificanceClassification,
    ChangeType,
)
from src.models.state import ProcessingState

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def synthesize_baseline(
    baseline: BaselineDocument,
    api_key: str,
    model: str = "claude-sonnet-4-6",
) -> dict:
    client = anthropic.AsyncAnthropic(api_key=api_key)

    scan_summary = baseline.model_dump_json(indent=2, exclude={"external_references"})
    if len(scan_summary) > 50000:
        for svc in baseline.services:
            svc.exposed_apis = svc.exposed_apis[:20]
            svc.consumed_apis = svc.consumed_apis[:10]
        scan_summary = baseline.model_dump_json(indent=2, exclude={"external_references"})

    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        temperature=0,
        system=SYSTEM_PROMPT,
        tools=[SYNTHESIS_TOOL],
        tool_choice={"type": "tool", "name": "synthesize_baseline"},
        messages=[{
            "role": "user",
            "content": f"Synthesize this codebase scan into an Architecture Baseline:\n\n{scan_summary}",
        }],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input
    return {}


def handle_uncertain_findings(
    baseline: BaselineDocument,
    state: ProcessingState,
) -> BaselineDocument:
    for unknown in baseline.flagged_unknowns:
        review = MultiAgentReview(
            perspectives=[
                PerspectiveResult(
                    perspective="baseline_scanner",
                    classification=SignificanceClassification(
                        significance=Significance.MODERATE,
                        change_type=ChangeType.INFRASTRUCTURE,
                        confidence=Confidence.BORDERLINE,
                        summary=unknown.description,
                        rationale="Uncertain finding during baseline scan",
                        affected_services=[],
                    ),
                )
            ],
            consensus=False,
            escalation_triggered=True,
            escalation_reason="Uncertain baseline finding",
        )

        review = evaluate_escalation(review, state)

        if not review.escalation_triggered:
            unknown.status = "resolved"
            unknown.resolution = "Auto-resolved via precedent"

    return baseline


async def write_baseline(
    baseline: BaselineDocument,
    arch_repo_dir: Path,
    api_key: str,
    state: ProcessingState,
    model: str = "claude-sonnet-4-6",
) -> Path:
    synthesis = await synthesize_baseline(baseline, api_key, model)

    for desc in synthesis.get("service_descriptions", []):
        for svc in baseline.services:
            if svc.name == desc["service_name"]:
                svc.responsibility = desc["responsibility"]

    for flagged in synthesis.get("flagged_unknowns", []):
        baseline.flagged_unknowns.append(FlaggedUnknown(
            description=flagged["description"],
            location=flagged.get("location", ""),
        ))

    baseline = handle_uncertain_findings(baseline, state)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("baseline_document.md.j2")
    rendered = template.render(baseline=baseline)

    baseline_path = arch_repo_dir / "ARCHITECTURE_BASELINE.md"
    baseline_path.write_text(rendered)

    return baseline_path


def archive_baseline(arch_repo_dir: Path, version: int) -> Path | None:
    current = arch_repo_dir / "ARCHITECTURE_BASELINE.md"
    if current.exists():
        archive_name = f"ARCHITECTURE_BASELINE_v{version}.md"
        archive_path = arch_repo_dir / archive_name
        archive_path.write_text(current.read_text())
        return archive_path
    return None
