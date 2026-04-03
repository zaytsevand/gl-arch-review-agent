from datetime import datetime

from src.models.state import MRState, ProcessingState
from src.services.baseline_detector import (
    check_baseline_exists,
    check_staleness,
    validate_baseline_content,
)


VALID_BASELINE = """# Architecture Baseline

## 1. Service Inventory

| Service | Port | Framework |
|---------|------|-----------|
| order-service | 8080 | Spring Boot 3.2.3 |
| payment-service | 8081 | Spring Boot 3.2.3 |

## 2. Communication Patterns

order-service calls payment-service via REST at /api/payments.
The integration uses RestTemplate with a configured base URL.
"""

EMPTY_BASELINE = """# Architecture Baseline

## 1. Service Inventory

[placeholder]

## 2. Communication Patterns

[TODO]
"""

MISSING_SECTIONS = """# Architecture Baseline

## 1. Service Inventory

| Service | Port |
|---------|------|
| order-service | 8080 |

Some content here that is long enough to be substantive for the section.
"""


def test_check_baseline_absent(tmp_path):
    assert check_baseline_exists(tmp_path) == "absent"


def test_check_baseline_empty_file(tmp_path):
    (tmp_path / "ARCHITECTURE_BASELINE.md").write_text("")
    assert check_baseline_exists(tmp_path) == "absent"


def test_check_baseline_too_short(tmp_path):
    (tmp_path / "ARCHITECTURE_BASELINE.md").write_text("# Baseline\n\nShort.")
    assert check_baseline_exists(tmp_path) == "absent"


def test_check_baseline_valid(tmp_path):
    (tmp_path / "ARCHITECTURE_BASELINE.md").write_text(VALID_BASELINE)
    assert check_baseline_exists(tmp_path) == "valid"


def test_validate_content_with_placeholders():
    assert validate_baseline_content(EMPTY_BASELINE) == "invalid"


def test_validate_content_missing_communication():
    assert validate_baseline_content(MISSING_SECTIONS) == "invalid"


def test_validate_content_valid():
    assert validate_baseline_content(VALID_BASELINE) == "valid"


def test_staleness_no_mrs():
    state = ProcessingState(baseline_generated_at=datetime(2026, 4, 1))
    assert check_staleness(state) is False


def test_staleness_below_threshold():
    state = ProcessingState(
        baseline_generated_at=datetime(2026, 4, 1),
        analyzed_mrs={
            "g/s!1": MRState(project_path="g/s", mr_iid=1, significance="high"),
            "g/s!2": MRState(project_path="g/s", mr_iid=2, significance="moderate"),
        },
    )
    assert check_staleness(state) is False


def test_staleness_above_threshold():
    state = ProcessingState(
        baseline_generated_at=datetime(2026, 4, 1),
        analyzed_mrs={
            "g/s!1": MRState(project_path="g/s", mr_iid=1, significance="high"),
            "g/s!2": MRState(project_path="g/s", mr_iid=2, significance="high"),
            "g/s!3": MRState(project_path="g/s", mr_iid=3, significance="high"),
        },
    )
    assert check_staleness(state) is True


def test_staleness_no_baseline_date():
    state = ProcessingState()
    assert check_staleness(state) is False


def test_staleness_infra_change_triggers():
    """Infrastructure changes should trigger staleness even below high threshold."""
    state = ProcessingState(
        baseline_generated_at=datetime(2026, 4, 1),
        analyzed_mrs={
            "g/s!1": MRState(
                project_path="g/s", mr_iid=1,
                significance="moderate", change_type="infrastructure",
            ),
        },
    )
    assert check_staleness(state) is True


def test_staleness_config_change_triggers():
    """Config changes should trigger staleness."""
    state = ProcessingState(
        baseline_generated_at=datetime(2026, 4, 1),
        analyzed_mrs={
            "g/s!1": MRState(
                project_path="g/s", mr_iid=1,
                significance="moderate", change_type="config_change",
            ),
        },
    )
    assert check_staleness(state) is True


def test_staleness_non_infra_change_no_trigger():
    """Non-infra moderate changes should not trigger staleness."""
    state = ProcessingState(
        baseline_generated_at=datetime(2026, 4, 1),
        analyzed_mrs={
            "g/s!1": MRState(
                project_path="g/s", mr_iid=1,
                significance="moderate", change_type="api_change",
            ),
        },
    )
    assert check_staleness(state) is False
