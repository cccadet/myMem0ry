"""Tests for hook payload sanitization and routing."""

from __future__ import annotations

import pytest
from pathlib import Path

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema
from mem0ry.hooks.sanitize import sanitize_payload
from mem0ry.hooks.router import handle_hook_event


class TestSanitize:
    def test_basic_payload(self) -> None:
        result = sanitize_payload(
            {
                "kind": "session-start",
                "session_id": "abc123",
                "cwd": "/home/user/project",
            }
        )
        assert result["kind"] == "session-start"
        assert result["session_id"] == "abc123"

    def test_invalid_kind_becomes_other(self) -> None:
        result = sanitize_payload(
            {
                "kind": "made-up-event",
                "session_id": "abc",
            }
        )
        assert result["kind"] == "other"

    def test_missing_session_id_raises(self) -> None:
        with pytest.raises(ValueError, match="session_id"):
            sanitize_payload({"kind": "session-start"})

    def test_strips_api_keys(self) -> None:
        result = sanitize_payload(
            {
                "kind": "user-prompt",
                "session_id": "abc",
                "body": "my key is sk-abc123def456ghi789jkl012mno345",
            }
        )
        assert "sk-abc123" not in result["body"]
        assert "[REDACTED]" in result["body"]

    def test_strips_bearer_tokens(self) -> None:
        result = sanitize_payload(
            {
                "kind": "user-prompt",
                "session_id": "abc",
                "body": "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            }
        )
        assert "eyJhbGci" not in result["body"]
        assert "[REDACTED]" in result["body"]

    def test_strips_home_paths(self) -> None:
        result = sanitize_payload(
            {
                "kind": "session-start",
                "session_id": "abc",
                "body": "file at /home/johndoe/project/main.py",
            }
        )
        assert "/home/johndoe" not in result["body"]
        assert "~/project/main.py" in result["body"]

    def test_truncates_long_body(self) -> None:
        result = sanitize_payload(
            {
                "kind": "user-prompt",
                "session_id": "abc",
                "body": "x" * 20_000,
            }
        )
        assert len(result["body"]) <= 10_100

    def test_non_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="dict"):
            sanitize_payload("not a dict")

    def test_none_body_stays_none(self) -> None:
        result = sanitize_payload(
            {
                "kind": "session-start",
                "session_id": "abc",
            }
        )
        assert result["body"] is None


class TestRouter:
    @pytest.fixture()
    def db(self, tmp_path: Path) -> Path:
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        init_schema(conn)
        conn.close()
        return db_path

    def test_basic_event(self, db: Path) -> None:
        obs_id = handle_hook_event(
            db,
            {
                "kind": "session-start",
                "session_id": "s1",
                "cwd": "/tmp/test",
                "agent": "claude-code",
            },
        )
        assert len(obs_id) == 12

    def test_session_end_creates_handoff(self, db: Path) -> None:
        handle_hook_event(
            db,
            {
                "kind": "session-start",
                "session_id": "s1",
                "cwd": "/tmp/test",
                "agent": "claude-code",
            },
        )
        handle_hook_event(
            db,
            {
                "kind": "user-prompt",
                "session_id": "s1",
                "body": "fix the bug",
                "agent": "claude-code",
            },
        )
        handle_hook_event(
            db,
            {
                "kind": "session-end",
                "session_id": "s1",
                "cwd": "/tmp/test",
                "agent": "claude-code",
            },
        )

        from mem0ry.db.store import pending_handoff

        ho = pending_handoff(db, project_id=None)
        assert ho is not None
        assert "session-start" in ho["summary"] or "user-prompt" in ho["summary"]

    def test_session_end_with_messages_archives_conversation(
        self, db: Path, tmp_path: Path
    ) -> None:
        conv_dir = tmp_path / "conv"
        conv_dir.mkdir()

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("CONVERSATIONS_DIR", str(conv_dir))

            handle_hook_event(
                db,
                {
                    "kind": "session-end",
                    "session_id": "s-archive",
                    "cwd": str(tmp_path),
                    "agent": "test",
                    "title": "Archived Chat",
                    "messages": [
                        {"role": "user", "content": "hello"},
                        {"role": "assistant", "content": "hi there"},
                    ],
                    "body": "A chat about greetings",
                },
            )

        from mem0ry.db.store import get_session_observations

        obs = get_session_observations(db, "s-archive")
        assert len(obs) >= 1

    def test_log_kind_creates_session_memory(self, db: Path) -> None:
        handle_hook_event(
            db,
            {
                "kind": "log",
                "session_id": "s-log",
                "body": "quick log entry",
                "title": "Test Log",
                "cwd": "/tmp/test",
            },
        )

        from mem0ry.db.store import search_memories

        results = search_memories(db, scope="session", top_k=10)
        assert any("quick log entry" in r["content"] for r in results)

    def test_secrets_stripped_before_storage(self, db: Path) -> None:
        handle_hook_event(
            db,
            {
                "kind": "user-prompt",
                "session_id": "s1",
                "body": "my key is sk-abc123def456ghi789jkl012mno345pqr678",
                "agent": "test",
            },
        )

        from mem0ry.db.store import get_session_observations

        obs = get_session_observations(db, "s1")
        assert len(obs) == 1
        assert "sk-abc123" not in (obs[0]["body"] or "")
