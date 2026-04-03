from __future__ import annotations

import re
from pathlib import Path

from src.models.state import ProcessingState

BASELINE_FILENAME = "ARCHITECTURE_BASELINE.md"

MANDATORY_SECTIONS = [
    "Service Inventory",
    "Communication Patterns",
]

# File patterns that indicate infrastructure changes
INFRA_FILE_PATTERNS = [
    re.compile(r"(?:^|/)Dockerfile(?:\.|$)", re.IGNORECASE),
    re.compile(r"(?:^|/)docker-compose", re.IGNORECASE),
    re.compile(r"\.gitlab-ci\.yml$"),
    re.compile(r"(?:^|/)k8s/"),
    re.compile(r"(?:^|/)kubernetes/"),
    re.compile(r"(?:^|/)helm/"),
    re.compile(r"(?:^|/)terraform/"),
    re.compile(r"\.tf$"),
]


def check_baseline_exists(arch_repo_dir: Path) -> str:
    baseline_path = arch_repo_dir / BASELINE_FILENAME
    if not baseline_path.exists():
        return "absent"

    content = baseline_path.read_text()
    if len(content.strip()) < 100:
        return "absent"

    return validate_baseline_content(content)


def validate_baseline_content(content: str) -> str:
    for section in MANDATORY_SECTIONS:
        pattern = rf"##?\s+.*{re.escape(section)}"
        section_match = re.search(pattern, content, re.IGNORECASE)
        if not section_match:
            return "invalid"

        section_start = section_match.end()
        next_section = re.search(r'\n##?\s+', content[section_start:])
        section_end = section_start + next_section.start() if next_section else len(content)
        section_content = content[section_start:section_end].strip()

        if len(section_content) < 50:
            return "invalid"

        if re.search(r'\[placeholder\]|\[TODO\]|\[TBD\]', section_content, re.IGNORECASE):
            return "invalid"

    return "valid"


def check_staleness(
    state: ProcessingState,
    high_significance_threshold: int = 3,
) -> bool:
    if not state.analyzed_mrs:
        return False

    baseline_date = getattr(state, "baseline_generated_at", None)
    if baseline_date is None:
        return False

    high_count = 0
    infra_change = False

    for mr_state in state.analyzed_mrs.values():
        if mr_state.significance == "high":
            high_count += 1

        # Check if any analyzed MR involved infrastructure changes
        if mr_state.change_type:
            if mr_state.change_type in ("infrastructure", "config_change"):
                infra_change = True

    if high_count >= high_significance_threshold:
        return True

    return infra_change
