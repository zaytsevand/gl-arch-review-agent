from datetime import date
from pathlib import Path

import pytest

from src.models.classification import (
    ChangeType,
    Confidence,
    MultiAgentReview,
    PerspectiveResult,
    Significance,
    SignificanceClassification,
)
from src.models.output import ADLEntry
from src.services.adl_writer import (
    append_entry,
    read_and_extend_adl,
    update_entry,
)
from src.services.state_manager import StateManager


SAMPLE_ADL = """# Architecture Decision Log

This document tracks all architecturally significant changes.

| # | Date | Service | Change Type | Summary | ADR |
|---|------|---------|-------------|---------|-----|

<!-- New entries should be added above this line -->
"""

EXTENDED_ADL = """# Architecture Decision Log

This document tracks all architecturally significant changes.

| # | Date | Service | Change Type | Confidence | Summary | Rationale | ADR |
|---|------|---------|-------------|------------|---------|-----------|-----|

<!-- New entries should be added above this line -->
"""


def test_read_and_extend_original_format(tmp_path):
    adl_path = tmp_path / "ADL.md"
    adl_path.write_text(SAMPLE_ADL)
    content = read_and_extend_adl(adl_path)
    assert "Confidence" in content
    assert "Rationale" in content


def test_read_and_extend_already_extended(tmp_path):
    adl_path = tmp_path / "ADL.md"
    adl_path.write_text(EXTENDED_ADL)
    content = read_and_extend_adl(adl_path)
    assert content.count("Confidence") == 1


def test_read_and_extend_missing_file(tmp_path):
    adl_path = tmp_path / "ADL.md"
    content = read_and_extend_adl(adl_path)
    assert "Architecture Decision Log" in content
    assert "Confidence" in content


def test_append_entry():
    entry = ADLEntry(
        number=1,
        date=date(2026, 4, 3),
        service="order-service",
        change_type="Api Change",
        confidence="High",
        summary="New V2 endpoint",
        rationale="Adds API versioning",
        adr_link="adr/001.md",
    )
    result = append_entry(EXTENDED_ADL, entry)
    assert "| 1 |" in result
    assert "order-service" in result
    assert "adr/001.md" in result
    assert result.index("| 1 |") < result.index("<!-- New entries")


def test_append_multiple_entries():
    entry1 = ADLEntry(
        number=1, date=date(2026, 4, 3), service="svc1",
        change_type="Api Change", confidence="High",
        summary="First", rationale="reason1",
    )
    entry2 = ADLEntry(
        number=2, date=date(2026, 4, 3), service="svc2",
        change_type="New Dependency", confidence="Medium",
        summary="Second", rationale="reason2",
    )
    content = append_entry(EXTENDED_ADL, entry1)
    content = append_entry(content, entry2)
    assert "| 1 |" in content
    assert "| 2 |" in content


def test_update_entry():
    content = EXTENDED_ADL.replace(
        "<!-- New entries",
        "| 1 | 2026-04-03 | svc | old | High | old summary | old rationale | - |\n<!-- New entries",
    )
    new_entry = ADLEntry(
        number=1, date=date(2026, 4, 3), service="svc",
        change_type="Api Change", confidence="High",
        summary="UPDATED summary", rationale="UPDATED rationale",
    )
    result = update_entry(content, 1, new_entry)
    assert "UPDATED summary" in result
    assert "old summary" not in result


def test_entry_no_adr_shows_dash():
    entry = ADLEntry(
        number=1, date=date(2026, 4, 3), service="svc",
        change_type="Refactoring", confidence="Medium",
        summary="Extracted validation", rationale="Design pattern",
    )
    result = append_entry(EXTENDED_ADL, entry)
    assert "| - |" in result
