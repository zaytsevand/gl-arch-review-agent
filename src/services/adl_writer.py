from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.models.classification import MultiAgentReview, Significance
from src.models.output import ADLEntry
from src.services.state_manager import StateManager

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

EXTENDED_HEADER = "| # | Date | Service | Change Type | Confidence | Summary | Rationale | ADR |"
EXTENDED_SEPARATOR = "|---|------|---------|-------------|------------|---------|-----------|-----|"
INSERT_MARKER = "<!-- New entries should be added above this line -->"


def _confidence_label(review: MultiAgentReview) -> str:
    if review.consensus_confidence:
        return review.consensus_confidence.value.capitalize()
    return "Medium"


def build_adl_entry(
    review: MultiAgentReview,
    state_manager: StateManager,
    service_name: str,
    adr_link: str | None = None,
) -> ADLEntry:
    first = review.perspectives[0].classification if review.perspectives else None
    if not first:
        return ADLEntry(
            number=state_manager.next_adl_number(),
            date=date.today(),
            service=service_name,
            change_type="unknown",
            confidence=_confidence_label(review),
            summary="Classification failed",
            rationale="No perspective results available",
            adr_link=adr_link,
        )

    return ADLEntry(
        number=state_manager.next_adl_number(),
        date=date.today(),
        service=service_name,
        change_type=first.change_type.value.replace("_", " ").title(),
        confidence=_confidence_label(review),
        summary=first.summary[:120],
        rationale=first.rationale,
        adr_link=adr_link,
    )


def read_and_extend_adl(adl_path: Path) -> str:
    if not adl_path.exists():
        return (
            "# Architecture Decision Log\n\n"
            "This document tracks all architecturally significant changes.\n\n"
            f"{EXTENDED_HEADER}\n{EXTENDED_SEPARATOR}\n\n{INSERT_MARKER}\n"
        )

    content = adl_path.read_text()

    original_header_pattern = r"\| # \| Date \| Service \| Change Type \| Summary \| ADR \|"
    if re.search(original_header_pattern, content) and "Confidence" not in content:
        content = re.sub(
            r"\| # \| Date \| Service \| Change Type \| Summary \| ADR \|",
            EXTENDED_HEADER,
            content,
        )
        content = re.sub(
            r"\|---\|------\|---------|-------------|---------|-----\|",
            EXTENDED_SEPARATOR,
            content,
        )

    return content


def append_entry(adl_content: str, entry: ADLEntry) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("adl_entry.md.j2")
    row = template.render(entry=entry)

    if INSERT_MARKER in adl_content:
        return adl_content.replace(INSERT_MARKER, f"{row}\n{INSERT_MARKER}")

    return adl_content.rstrip() + "\n" + row + "\n"


def update_entry(adl_content: str, entry_number: int, new_entry: ADLEntry) -> str:
    pattern = rf"^\| {entry_number} \|.*$"
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("adl_entry.md.j2")
    new_row = template.render(entry=new_entry)
    updated = re.sub(pattern, new_row, adl_content, flags=re.MULTILINE)
    return updated


def write_adl(
    adl_path: Path,
    review: MultiAgentReview,
    state_manager: StateManager,
    service_name: str,
    adr_link: str | None = None,
    existing_entry_number: int | None = None,
) -> ADLEntry:
    content = read_and_extend_adl(adl_path)

    if existing_entry_number is not None:
        entry = ADLEntry(
            number=existing_entry_number,
            date=date.today(),
            service=service_name,
            change_type=review.perspectives[0].classification.change_type.value.replace("_", " ").title()
            if review.perspectives
            else "unknown",
            confidence=_confidence_label(review),
            summary=review.perspectives[0].classification.summary[:120]
            if review.perspectives
            else "",
            rationale=review.perspectives[0].classification.rationale
            if review.perspectives
            else "",
            adr_link=adr_link,
        )
        content = update_entry(content, existing_entry_number, entry)
    else:
        entry = build_adl_entry(review, state_manager, service_name, adr_link)
        content = append_entry(content, entry)

    adl_path.write_text(content)
    return entry


def read_ci_config(repo_dir: Path) -> dict:
    config: dict = {"disabled_rules": []}

    # Check GitLab CI
    ci_path = repo_dir / ".gitlab-ci.yml"
    if ci_path.exists():
        ci_content = ci_path.read_text()
        disabled_matches = re.findall(r"--disable\s+(MD\d+)", ci_content)
        config["disabled_rules"].extend(disabled_matches)

    # Check GitHub Actions workflows
    workflows_dir = repo_dir / ".github" / "workflows"
    if workflows_dir.is_dir():
        for wf in workflows_dir.glob("*.yml"):
            wf_content = wf.read_text()
            disabled_matches = re.findall(r"--disable\s+(MD\d+)", wf_content)
            config["disabled_rules"].extend(disabled_matches)
        for wf in workflows_dir.glob("*.yaml"):
            wf_content = wf.read_text()
            disabled_matches = re.findall(r"--disable\s+(MD\d+)", wf_content)
            config["disabled_rules"].extend(disabled_matches)

    markdownlint_path = repo_dir / ".markdownlint.json"
    if markdownlint_path.exists():
        import json

        try:
            lint_config = json.loads(markdownlint_path.read_text())
            for rule, enabled in lint_config.items():
                if not enabled and rule.startswith("MD"):
                    config["disabled_rules"].append(rule)
        except (json.JSONDecodeError, AttributeError):
            pass

    return config
