"""Tests for handoffs CRUD."""

from __future__ import annotations

import pytest
from pathlib import Path

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema
from mem0ry.db.store import (
    auto_handoff_from_session,
    begin_handoff,
    accept_handoff,
    create_observation,
    pending_handoff,
)


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()
    return db_path


def test_begin_handoff_basic(db: Path) -> None:
    ho_id = begin_handoff(
        db,
        session_id="sess1",
        from_agent="claude-code",
        summary="Worked on auth refactor",
        project_id="github.com/user/project",
    )
    assert len(ho_id) == 12

    ho = pending_handoff(db, project_id="github.com/user/project")
    assert ho is not None
    assert ho["status"] == "open"
    assert ho["summary"] == "Worked on auth refactor"
    assert ho["from_agent"] == "claude-code"


def test_begin_handoff_with_extras(db: Path) -> None:
    begin_handoff(
        db,
        session_id="sess1",
        from_agent="opencode",
        summary="Debugging",
        open_questions=["Why does auth fail?"],
        next_steps=["Check JWT expiry"],
    )
    ho = pending_handoff(db, project_id=None)
    assert ho is not None
    assert ho["open_questions"] == ["Why does auth fail?"]
    assert ho["next_steps"] == ["Check JWT expiry"]


def test_accept_handoff_marks_accepted(db: Path) -> None:
    begin_handoff(
        db,
        session_id="sess1",
        from_agent="claude-code",
        summary="Worked on X",
        project_id="github.com/user/project",
    )

    ho = accept_handoff(db, project_id="github.com/user/project", accepted_by="codex")
    assert ho is not None
    assert ho["status"] == "accepted"
    assert ho["accepted_by"] == "codex"
    assert ho["accepted_at"] is not None

    ho2 = pending_handoff(db, project_id="github.com/user/project")
    assert ho2 is None


def test_accept_handoff_no_match(db: Path) -> None:
    begin_handoff(
        db,
        session_id="sess1",
        from_agent="claude-code",
        summary="Worked on X",
        project_id="github.com/user/project-a",
    )

    ho = accept_handoff(db, project_id="github.com/user/project-b")
    assert ho is None


def test_accept_returns_none_when_empty(db: Path) -> None:
    ho = accept_handoff(db, project_id=None)
    assert ho is None


def test_pending_handoff_returns_latest(db: Path) -> None:
    begin_handoff(
        db, session_id="s1", from_agent="a1", summary="first", project_id="p1"
    )
    begin_handoff(
        db, session_id="s2", from_agent="a2", summary="second", project_id="p1"
    )

    ho = pending_handoff(db, project_id="p1")
    assert ho is not None
    assert ho["summary"] == "second"


def test_auto_handoff_from_session(db: Path) -> None:
    create_observation(
        db, session_id="s1", kind="session-start", body="start", project_id="p1"
    )
    create_observation(
        db, session_id="s1", kind="user-prompt", body="fix auth", project_id="p1"
    )
    create_observation(
        db, session_id="s1", kind="session-end", body="end", project_id="p1"
    )

    ho_id = auto_handoff_from_session(db, "s1", "claude-code")
    assert ho_id is not None

    ho = pending_handoff(db, project_id="p1")
    assert ho is not None
    assert "session-start" in ho["summary"]


def test_auto_handoff_skips_if_exists(db: Path) -> None:
    create_observation(db, session_id="s1", kind="session-start", body="start")
    begin_handoff(db, session_id="s1", from_agent="manual", summary="manual handoff")

    result = auto_handoff_from_session(db, "s1", "claude-code")
    assert result is None


def test_auto_handoff_empty_session(db: Path) -> None:
    result = auto_handoff_from_session(db, "nonexistent", "claude-code")
    assert result is None
