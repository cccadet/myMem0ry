"""Tests for observations CRUD."""

from __future__ import annotations

import pytest
from pathlib import Path

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema
from mem0ry.db.store import create_observation, get_session_observations


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def test_create_observation_basic(db: Path) -> None:
    obs_id = create_observation(db, session_id="sess1", kind="session-start")
    assert len(obs_id) == 12

    results = get_session_observations(db, "sess1")
    assert len(results) == 1
    assert results[0]["kind"] == "session-start"
    assert results[0]["session_id"] == "sess1"


def test_create_observation_with_all_fields(db: Path) -> None:
    obs_id = create_observation(
        db,
        session_id="sess2",
        kind="user-prompt",
        agent="claude-code",
        cwd="/home/user/project",
        project_id="github.com/user/project",
        title="User asked about auth",
        body="How do I implement JWT?",
    )
    assert len(obs_id) == 12

    results = get_session_observations(db, "sess2")
    assert len(results) == 1
    assert results[0]["agent"] == "claude-code"
    assert results[0]["project_id"] == "github.com/user/project"
    assert results[0]["title"] == "User asked about auth"


def test_invalid_kind_becomes_other(db: Path) -> None:
    create_observation(db, session_id="s1", kind="invalid-event")
    results = get_session_observations(db, "s1")
    assert results[0]["kind"] == "other"


def test_multiple_observations_ordered(db: Path) -> None:
    create_observation(db, session_id="s1", kind="session-start", body="start")
    create_observation(db, session_id="s1", kind="user-prompt", body="prompt")
    create_observation(db, session_id="s1", kind="session-end", body="end")

    results = get_session_observations(db, "s1")
    assert len(results) == 3
    assert results[0]["kind"] == "session-end"
    assert results[2]["kind"] == "session-start"


def test_filter_by_kind(db: Path) -> None:
    create_observation(db, session_id="s1", kind="session-start")
    create_observation(db, session_id="s1", kind="user-prompt")
    create_observation(db, session_id="s1", kind="user-prompt")

    results = get_session_observations(db, "s1", kind="user-prompt")
    assert len(results) == 2


def test_empty_session(db: Path) -> None:
    results = get_session_observations(db, "nonexistent")
    assert results == []
