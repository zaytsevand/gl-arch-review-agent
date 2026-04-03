import json
from datetime import datetime
from pathlib import Path

import pytest

from src.models.gitlab_types import CommitInfo
from src.services.state_manager import StateManager


@pytest.fixture
def state_path(tmp_path) -> Path:
    return tmp_path / ".agent-state.json"


@pytest.fixture
def state_manager(state_path) -> StateManager:
    return StateManager(state_path)


def test_fresh_state(state_manager):
    assert state_manager.state.version == "1.0"
    assert state_manager.state.adl_next_number == 1
    assert len(state_manager.state.analyzed_mrs) == 0


def test_save_and_reload(state_path, state_manager):
    state_manager.state.adl_next_number = 5
    state_manager.save()

    reloaded = StateManager(state_path)
    assert reloaded.state.adl_next_number == 5
    assert reloaded.state.last_run is not None


def test_has_changed_new_mr(state_manager, trivial_mr):
    assert state_manager.has_changed(trivial_mr) is True


def test_has_changed_unchanged_mr(state_manager, trivial_mr):
    state_manager.record_analysis(trivial_mr, "non_significant")
    assert state_manager.has_changed(trivial_mr) is False


def test_has_changed_after_new_commit(state_manager, trivial_mr):
    state_manager.record_analysis(trivial_mr, "non_significant")
    trivial_mr.commits = [
        CommitInfo(sha="newsha123", title="new commit", authored_date=datetime(2026, 4, 2))
    ]
    assert state_manager.has_changed(trivial_mr) is True


def test_has_changed_after_description_edit(state_manager, trivial_mr):
    state_manager.record_analysis(trivial_mr, "non_significant")
    trivial_mr.description = "Updated description with new info"
    assert state_manager.has_changed(trivial_mr) is True


def test_has_changed_after_new_discussion(state_manager, trivial_mr):
    state_manager.record_analysis(trivial_mr, "non_significant")
    from src.models.gitlab_types import Discussion, Note
    trivial_mr.discussions.append(
        Discussion(
            id="new",
            notes=[Note(author="reviewer", body="new comment", created_at=datetime(2026, 4, 2))],
        )
    )
    assert state_manager.has_changed(trivial_mr) is True


def test_record_analysis(state_manager, significant_mr):
    state_manager.record_analysis(significant_mr, "high", adl_entry_number=1, adr_file="adr/001.md")
    mr_state = state_manager.get_mr_state(significant_mr.project_path, significant_mr.mr_iid)
    assert mr_state is not None
    assert mr_state.significance == "high"
    assert mr_state.adl_entry_number == 1
    assert mr_state.adr_file == "adr/001.md"


def test_next_adl_number_increments(state_manager):
    assert state_manager.next_adl_number() == 1
    assert state_manager.next_adl_number() == 2
    assert state_manager.next_adl_number() == 3


def test_mr_key_format(state_manager):
    key = state_manager.mr_key("group/repo", 42)
    assert key == "group/repo!42"


def test_state_persists_json(state_path, state_manager, trivial_mr):
    state_manager.record_analysis(trivial_mr, "non_significant")
    state_manager.save()

    data = json.loads(state_path.read_text())
    assert "analyzed_mrs" in data
    assert "unlimit-test-agent/order-service!1" in data["analyzed_mrs"]


def test_save_uses_atomic_write(state_path, state_manager):
    """State save should use atomic write (no partial files on crash)."""
    state_manager.state.adl_next_number = 42
    state_manager.save()

    # Verify the file exists and has correct content
    data = json.loads(state_path.read_text())
    assert data["adl_next_number"] == 42

    # Verify no .tmp files left behind
    tmp_files = list(state_path.parent.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_save_uses_timezone_aware_datetime(state_path, state_manager):
    """last_run should be timezone-aware after save."""
    state_manager.save()
    assert state_manager.state.last_run is not None
    assert state_manager.state.last_run.tzinfo is not None
