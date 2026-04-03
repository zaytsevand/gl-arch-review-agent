from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import anthropic
from jinja2 import Environment, FileSystemLoader
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models.classification import MultiAgentReview
from src.models.output import ADRDocument, Alternative

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

ADR_GENERATION_TOOL = {
    "name": "generate_adr_content",
    "description": "Generate Architecture Decision Record content for a highly significant change",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "context": {"type": "string"},
            "decision": {"type": "string"},
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "reason_rejected": {"type": "string"},
                    },
                    "required": ["name", "reason_rejected"],
                },
            },
            "consequences": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["title", "context", "decision", "consequences"],
    },
}


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def generate_adr_content(
    review: MultiAgentReview,
    mr_title: str,
    mr_description: str,
    mr_url: str,
    api_key: str,
    model: str = "claude-sonnet-4-6",
) -> dict:
    client = anthropic.AsyncAnthropic(api_key=api_key)

    perspectives_summary = "\n".join(
        f"- {p.perspective}: {p.classification.significance.value} — {p.classification.rationale}"
        for p in review.perspectives
    )

    user_message = (
        f"## MR: {mr_title}\n"
        f"**URL**: {mr_url}\n"
        f"**Description**: {mr_description}\n\n"
        f"## Agent Assessments:\n{perspectives_summary}\n\n"
        "Generate a complete ADR for this architecturally significant change. "
        "Include meaningful alternatives and consequences."
    )

    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        temperature=0,
        system=(
            "You are an architecture documentation writer. Generate clear, concise "
            "Architecture Decision Records. Focus on the WHY, not the WHAT. "
            "Every sentence must carry information — no boilerplate."
        ),
        tools=[ADR_GENERATION_TOOL],
        tool_choice={"type": "tool", "name": "generate_adr_content"},
        messages=[{"role": "user", "content": user_message}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input
    return {}


async def write_adr(
    adr_dir: Path,
    number: int,
    review: MultiAgentReview,
    mr_title: str,
    mr_description: str,
    mr_urls: list[str],
    services: list[str],
    api_key: str,
    model: str = "claude-sonnet-4-6",
    dead_code_flags: list[str] | None = None,
) -> tuple[ADRDocument, Path]:
    content = await generate_adr_content(
        review, mr_title, mr_description, mr_urls[0] if mr_urls else "", api_key, model
    )

    consequences = content.get("consequences", [])
    if dead_code_flags:
        for flag in dead_code_flags:
            consequences.append(f"Dead code / incomplete integration: {flag}")

    adr = ADRDocument(
        number=number,
        title=content.get("title", mr_title),
        date=date.today(),
        confidence=review.consensus_confidence.value.capitalize()
        if review.consensus_confidence
        else "Medium",
        services=services,
        source_mr_urls=mr_urls,
        context=content.get("context", ""),
        decision=content.get("decision", ""),
        alternatives=[
            Alternative(**alt) for alt in content.get("alternatives", [])
        ],
        consequences=consequences,
    )

    slug = _slugify(adr.title)
    filename = f"{number:03d}-{slug}.md"
    adr_path = adr_dir / filename

    adr_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("adr_document.md.j2")
    rendered = template.render(adr=adr)
    adr_path.write_text(rendered)

    return adr, adr_path
