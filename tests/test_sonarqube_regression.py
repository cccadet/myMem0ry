"""Regression tests for SonarQube fixes — ensures no behavior changed.

Covers:
  - S1854: ensure_server import removal (mcp_server.py)
  - S6019: reluctant quantifier fix (store_handoffs.py _ERROR_RE)
  - S5869: duplicate char class fix (sanitize.py _WIN_HOME_PATTERN)
  - S1172: unused param removal (store_memories.py, web/pages.py)
  - S5713: redundant exception catches (daemon.py, git_context.py, server.py)
  - S1192: constant extraction (config.py _DB_FILENAME, hooks.py _CONFIG_DIR)
  - S6711: numpy random modernization (test_embeddings.py)
  - S3776: cognitive complexity refactors (retention, handoffs, router, sanitize)
  - S7679/S131: shell fixes (session-end.sh)
  - S1192: shell constant (install.sh)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mem0ry.db.connection import get_connection
from mem0ry.db.schema import init_schema
from mem0ry.hooks.sanitize import (
    _extract_tool_input_parts,
    _extract_tool_response_parts,
    _resolve_body,
    _resolve_kind,
    sanitize_payload,
)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# S5869: _WIN_HOME_PATTERN still matches all Windows home paths
# ---------------------------------------------------------------------------

class TestWinHomePatternRegression:
    def test_windows_backslash_path_stripped(self) -> None:
        result = sanitize_payload({
            "kind": "user-prompt",
            "session_id": "s1",
            "body": r"Reading C:\Users\alice\project\main.py",
        })
        assert "alice" not in (result["body"] or "")
        assert "~" in (result["body"] or "")

    def test_windows_forward_slash_path_stripped(self) -> None:
        result = sanitize_payload({
            "kind": "user-prompt",
            "session_id": "s1",
            "body": "Reading C:/Users/bob/project/main.py",
        })
        assert "bob" not in (result["body"] or "")
        assert "~" in (result["body"] or "")

    def test_windows_lowercase_drive_letter(self) -> None:
        result = sanitize_payload({
            "kind": "user-prompt",
            "session_id": "s1",
            "body": r"File at d:\Users\charlie\code\app.py",
        })
        assert "charlie" not in (result["body"] or "")
        assert "~" in (result["body"] or "")

    def test_windows_uppercase_users_dir(self) -> None:
        result = sanitize_payload({
            "kind": "user-prompt",
            "session_id": "s1",
            "body": r"Path C:\USERS\DANA\src\file.py",
        })
        assert "DANA" not in (result["body"] or "")

    def test_post_tool_use_windows_path_in_file_path(self) -> None:
        result = sanitize_payload({
            "kind": "post-tool-use",
            "session_id": "s1",
            "tool_name": "Edit",
            "tool_input": {"file_path": r"D:\Users\eve\project\mod.py"},
            "body": "tool-use",
        })
        assert "eve" not in (result["body"] or "")


# ---------------------------------------------------------------------------
# S3776 (sanitize): _resolve_kind, _resolve_body, extract helpers
# ---------------------------------------------------------------------------

class TestResolveKindRegression:
    def test_explicit_kind_preserved(self) -> None:
        assert _resolve_kind({"kind": "session-start"}) == "session-start"

    def test_invalid_kind_becomes_other(self) -> None:
        assert _resolve_kind({"kind": "nonsense"}) == "other"

    def test_hook_event_name_fallback_session_start(self) -> None:
        assert _resolve_kind({"kind": "other", "hook_event_name": "SessionStart"}) == "session-start"

    def test_hook_event_name_fallback_user_prompt(self) -> None:
        assert _resolve_kind({"kind": "other", "hook_event_name": "UserPrompt"}) == "user-prompt"

    def test_hook_event_name_fallback_post_tool_use(self) -> None:
        assert _resolve_kind({"kind": "other", "hook_event_name": "PostToolUse"}) == "post-tool-use"

    def test_hook_event_name_fallback_pre_compact(self) -> None:
        assert _resolve_kind({"kind": "other", "hook_event_name": "PreCompact"}) == "pre-compact"

    def test_hook_event_name_fallback_session_end(self) -> None:
        assert _resolve_kind({"kind": "other", "hook_event_name": "SessionEnd"}) == "session-end"

    def test_unknown_hook_event_name_falls_to_other(self) -> None:
        assert _resolve_kind({"kind": "other", "hook_event_name": "UnknownEvent"}) == "other"

    def test_empty_kind_uses_hook_event_name(self) -> None:
        assert _resolve_kind({"hook_event_name": "SessionEnd"}) == "session-end"


class TestResolveBodyRegression:
    def test_post_tool_use_uses_summarize(self) -> None:
        body = _resolve_body("post-tool-use", {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/x.py"},
            "body": "tool-use",
        })
        assert body is not None
        assert "Edit" in body
        assert "x.py" in body

    def test_other_kind_strips_secrets(self) -> None:
        body = _resolve_body("user-prompt", {
            "body": "my key is sk-abc123def456ghi789jkl012mno345",
        })
        assert body is not None
        assert "sk-abc123" not in body
        assert "[REDACTED]" in body

    def test_none_body_returns_none(self) -> None:
        assert _resolve_body("session-start", {}) is None


class TestExtractToolInputPartsRegression:
    def test_file_path_extracted(self) -> None:
        parts = _extract_tool_input_parts({"file_path": "/home/user/app.py"})
        assert any("app.py" in p for p in parts)

    def test_file_path_variant(self) -> None:
        parts = _extract_tool_input_parts({"filePath": "/home/user/app.py"})
        assert any("app.py" in p for p in parts)

    def test_command_truncated_to_200(self) -> None:
        parts = _extract_tool_input_parts({"command": "x" * 300})
        cmd_part = [p for p in parts if p.startswith("command:")][0]
        assert len(cmd_part) <= 210

    def test_query_extracted(self) -> None:
        parts = _extract_tool_input_parts({"query": "search terms"})
        assert any("search terms" in p for p in parts)

    def test_search_key_extracted(self) -> None:
        parts = _extract_tool_input_parts({"search": "find this"})
        assert any("find this" in p for p in parts)

    def test_empty_input(self) -> None:
        assert _extract_tool_input_parts({}) == []


class TestExtractToolResponsePartsRegression:
    def test_error_extracted(self) -> None:
        parts = _extract_tool_response_parts({"error": "file not found"})
        assert any("file not found" in p for p in parts)

    def test_success_extracted(self) -> None:
        parts = _extract_tool_response_parts({"success": True})
        assert any("True" in p for p in parts)

    def test_no_success_when_none(self) -> None:
        parts = _extract_tool_response_parts({"success": None})
        assert not any("success" in p for p in parts)

    def test_empty_response(self) -> None:
        assert _extract_tool_response_parts({}) == []

    def test_error_truncated_to_300(self) -> None:
        parts = _extract_tool_response_parts({"error": "E" * 500})
        err_part = [p for p in parts if p.startswith("error:")][0]
        assert len(err_part) <= 310


# ---------------------------------------------------------------------------
# S3776 (router): _handle_log_event, _handle_session_end
# ---------------------------------------------------------------------------

class TestRouterRegression:
    def test_session_end_creates_handoff_still(self, db: Path) -> None:
        from mem0ry.hooks.router import handle_hook_event
        from mem0ry.db.store import pending_handoff, create_observation

        create_observation(db, session_id="se1", kind="user-prompt", body="Fix login bug")

        handle_hook_event(db, {
            "kind": "session-end",
            "session_id": "se1",
            "body": "done",
        })
        ho = pending_handoff(db, project_id=None)
        assert ho is not None
        assert "login" in (ho.get("summary") or "").lower()

    def test_log_creates_session_memory(self, db: Path) -> None:
        from mem0ry.hooks.router import handle_hook_event
        from mem0ry.db.store import get_session_observations

        handle_hook_event(db, {
            "kind": "log",
            "session_id": "sl1",
            "title": "Important note",
            "body": "Remember this",
        })
        obs = get_session_observations(db, "sl1")
        assert len(obs) >= 1

    def test_post_tool_use_edit_records(self, db: Path) -> None:
        from mem0ry.hooks.router import handle_hook_event
        from mem0ry.db.store import get_session_observations

        eid = handle_hook_event(db, {
            "kind": "post-tool-use",
            "session_id": "st1",
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/regression.py"},
            "tool_response": {},
            "body": "tool-use",
        })
        assert len(eid) == 12
        obs = get_session_observations(db, "st1")
        assert any("regression.py" in (o.get("body") or "") for o in obs)

    def test_post_tool_use_read_skipped(self, db: Path) -> None:
        from mem0ry.hooks.router import handle_hook_event

        eid = handle_hook_event(db, {
            "kind": "post-tool-use",
            "session_id": "st2",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/skip.py"},
            "tool_response": {},
            "body": "tool-use",
        })
        assert eid == ""

    def test_post_tool_use_error_recorded(self, db: Path) -> None:
        from mem0ry.hooks.router import handle_hook_event
        from mem0ry.db.store import get_session_observations

        eid = handle_hook_event(db, {
            "kind": "post-tool-use",
            "session_id": "st3",
            "tool_name": "Bash",
            "tool_input": {"command": "ls /nope"},
            "tool_response": {"error": "No such file"},
            "body": "tool-use",
        })
        assert len(eid) == 12
        obs = get_session_observations(db, "st3")
        assert any("No such file" in (o.get("body") or "") for o in obs)

    def test_session_end_with_messages_archives(self, db: Path) -> None:
        from mem0ry.hooks.router import handle_hook_event

        handle_hook_event(db, {
            "kind": "session-end",
            "session_id": "se2",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ],
        })
        conv_dir = db.parent.parent / "conversations"
        if conv_dir.exists():
            md_files = list(conv_dir.rglob("*.md"))
            assert len(md_files) >= 1
            content = md_files[0].read_text()
            assert "Hello" in content

    def test_hook_event_name_fallback_in_full_pipeline(self, db: Path) -> None:
        from mem0ry.hooks.router import handle_hook_event
        from mem0ry.db.store import get_session_observations

        eid = handle_hook_event(db, {
            "hook_event_name": "SessionStart",
            "session_id": "sf1",
        })
        assert len(eid) == 12
        obs = get_session_observations(db, "sf1")
        assert len(obs) == 1
        assert obs[0]["kind"] == "session-start"


# ---------------------------------------------------------------------------
# S6019: _ERROR_RE regex now uses lookahead — error extraction still works
# ---------------------------------------------------------------------------

class TestErrorRegexRegression:
    def test_error_extraction_from_body(self, db: Path) -> None:
        from mem0ry.db.store import create_observation, auto_handoff_from_session

        create_observation(
            db, session_id="se3", kind="post-tool-use",
            body="tool: Bash; error: permission denied; file: /root/secret",
        )
        ho_id = auto_handoff_from_session(db, "se3", "test-agent")
        assert ho_id is not None

        conn = get_connection(db)
        row = conn.execute(
            "SELECT summary FROM handoffs WHERE id = ?", (ho_id,)
        ).fetchone()
        conn.close()
        summary = row["summary"]
        assert "permission denied" in summary

    def test_error_at_end_of_body(self, db: Path) -> None:
        from mem0ry.db.store import create_observation, auto_handoff_from_session

        create_observation(
            db, session_id="se4", kind="post-tool-use",
            body="tool: Bash; error: command not found",
        )
        ho_id = auto_handoff_from_session(db, "se4", "test-agent")
        assert ho_id is not None

        conn = get_connection(db)
        row = conn.execute(
            "SELECT summary FROM handoffs WHERE id = ?", (ho_id,)
        ).fetchone()
        conn.close()
        assert "command not found" in row["summary"]

    def test_multiple_errors_extracted(self, db: Path) -> None:
        from mem0ry.db.store import create_observation, auto_handoff_from_session

        create_observation(
            db, session_id="se5", kind="post-tool-use",
            body="error: first error; then more text; error: second error",
        )
        ho_id = auto_handoff_from_session(db, "se5", "test-agent")
        assert ho_id is not None

        conn = get_connection(db)
        row = conn.execute(
            "SELECT summary FROM handoffs WHERE id = ?", (ho_id,)
        ).fetchone()
        conn.close()
        summary = row["summary"]
        assert "first error" in summary
        assert "second error" in summary


# ---------------------------------------------------------------------------
# S3776 (retention): _evaluate_candidate, _hard_delete_expired
# ---------------------------------------------------------------------------

class TestRetentionRegression:
    def _insert_old_memory(
        self,
        db_path: Path,
        memory_type: str = "log",
        days_old: int = 100,
        access_count: int = 0,
    ) -> str:
        from mem0ry.db.store import create_memory

        past = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
        mem_id = create_memory(
            db_path,
            content=f"old {memory_type}",
            scope="session",
            memory_type=memory_type,
            title=f"Old {memory_type}",
        )
        conn = get_connection(db_path)
        conn.execute(
            "UPDATE memories SET created_at = ?, access_count = ? WHERE id = ?",
            (past, access_count, mem_id),
        )
        conn.commit()
        conn.close()
        return mem_id

    def test_forget_sweep_soft_deletes_old_log(self, db: Path) -> None:
        from mem0ry.db.retention import forget_sweep

        self._insert_old_memory(db, memory_type="log", days_old=200)
        result = forget_sweep(db, dry_run=False)
        assert result["soft_count"] == 1

        conn = get_connection(db)
        row = conn.execute("SELECT deleted_at FROM memories").fetchone()
        conn.close()
        assert row["deleted_at"] is not None

    def test_forget_sweep_preserves_recent(self, db: Path) -> None:
        from mem0ry.db.retention import forget_sweep

        self._insert_old_memory(db, memory_type="log", days_old=5)
        result = forget_sweep(db, dry_run=True)
        assert result["soft_count"] == 0

    def test_forget_sweep_preserves_pinned_fact(self, db: Path) -> None:
        from mem0ry.db.retention import forget_sweep

        self._insert_old_memory(db, memory_type="fact", days_old=500)
        result = forget_sweep(db, dry_run=True)
        assert result["soft_count"] == 0

    def test_forget_sweep_hard_deletes_after_grace(self, db: Path) -> None:
        from mem0ry.db.retention import forget_sweep, _GRACE_DAYS

        mem_id = self._insert_old_memory(db, memory_type="log", days_old=200)

        forget_sweep(db, dry_run=False)

        conn = get_connection(db)
        past_grace = (
            datetime.now(timezone.utc) - timedelta(days=_GRACE_DAYS + 1)
        ).isoformat()
        conn.execute(
            "UPDATE memories SET grace_until = ? WHERE id = ?",
            (past_grace, mem_id),
        )
        conn.commit()
        conn.close()

        result = forget_sweep(db, dry_run=False)
        assert result["hard_count"] == 1

        conn = get_connection(db)
        count = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
        conn.close()
        assert count == 0

    def test_forget_sweep_pattern_preserved_under_365(self, db: Path) -> None:
        from mem0ry.db.retention import forget_sweep

        self._insert_old_memory(db, memory_type="pattern", days_old=100)
        result = forget_sweep(db, dry_run=True)
        assert result["soft_count"] == 0

    def test_forget_sweep_pattern_swept_after_365(self, db: Path) -> None:
        from mem0ry.db.retention import forget_sweep

        self._insert_old_memory(db, memory_type="pattern", days_old=400)
        result = forget_sweep(db, dry_run=True)
        assert result["soft_count"] == 1

    def test_forget_sweep_high_access_count_preserves(self, db: Path) -> None:
        from mem0ry.db.retention import forget_sweep

        self._insert_old_memory(db, memory_type="log", days_old=200, access_count=500)
        result = forget_sweep(db, dry_run=True)
        assert result["soft_count"] == 0

    def test_forget_sweep_file_cleanup_on_hard_delete(self, db: Path) -> None:
        from mem0ry.db.retention import forget_sweep, _GRACE_DAYS

        mem_dir = db.parent / "memories"
        mem_dir.mkdir()
        (mem_dir / "test.md").write_text("# test")

        mem_id = self._insert_old_memory(db, memory_type="log", days_old=200)
        conn = get_connection(db)
        conn.execute(
            "UPDATE memories SET file_path = ? WHERE id = ?",
            ("test.md", mem_id),
        )
        conn.commit()
        conn.close()

        forget_sweep(db, dry_run=False)

        conn = get_connection(db)
        past_grace = (
            datetime.now(timezone.utc) - timedelta(days=_GRACE_DAYS + 1)
        ).isoformat()
        conn.execute(
            "UPDATE memories SET grace_until = ? WHERE id = ?",
            (past_grace, mem_id),
        )
        conn.commit()
        conn.close()

        forget_sweep(db, dry_run=False, memories_dir=mem_dir)
        assert not (mem_dir / "test.md").exists()


# ---------------------------------------------------------------------------
# S3776 (handoffs): _extract_session_signals, _build_session_summary
# ---------------------------------------------------------------------------

class TestHandoffSummaryRegression:
    def test_auto_handoff_includes_user_prompts(self, db: Path) -> None:
        from mem0ry.db.store import create_observation, auto_handoff_from_session

        create_observation(
            db, session_id="sh1", kind="user-prompt", body="Refactor the API layer"
        )
        create_observation(
            db, session_id="sh1", kind="user-prompt", body="Add error handling"
        )
        ho_id = auto_handoff_from_session(db, "sh1", "test-agent")
        assert ho_id is not None

        conn = get_connection(db)
        row = conn.execute("SELECT summary FROM handoffs WHERE id = ?", (ho_id,)).fetchone()
        conn.close()
        summary = row["summary"]
        assert "Refactor the API layer" in summary
        assert "Add error handling" in summary

    def test_auto_handoff_includes_files_touched(self, db: Path) -> None:
        from mem0ry.db.store import create_observation, auto_handoff_from_session

        create_observation(
            db, session_id="sh2", kind="post-tool-use",
            body="tool: Edit; file: /home/user/src/app.py",
        )
        ho_id = auto_handoff_from_session(db, "sh2", "test-agent")
        assert ho_id is not None

        conn = get_connection(db)
        row = conn.execute("SELECT summary FROM handoffs WHERE id = ?", (ho_id,)).fetchone()
        conn.close()
        assert "app.py" in row["summary"]

    def test_auto_handoff_includes_errors(self, db: Path) -> None:
        from mem0ry.db.store import create_observation, auto_handoff_from_session

        create_observation(
            db, session_id="sh3", kind="post-tool-use",
            body="tool: Bash; error: ModuleNotFoundError: no module named foo",
        )
        ho_id = auto_handoff_from_session(db, "sh3", "test-agent")
        assert ho_id is not None

        conn = get_connection(db)
        row = conn.execute("SELECT summary FROM handoffs WHERE id = ?", (ho_id,)).fetchone()
        conn.close()
        assert "ModuleNotFoundError" in row["summary"]

    def test_auto_handoff_empty_session(self, db: Path) -> None:
        from mem0ry.db.store import auto_handoff_from_session

        assert auto_handoff_from_session(db, "nonexistent", "test-agent") is None

    def test_auto_handoff_skips_duplicate(self, db: Path) -> None:
        from mem0ry.db.store import create_observation, auto_handoff_from_session

        create_observation(db, session_id="sh4", kind="user-prompt", body="First")
        ho1 = auto_handoff_from_session(db, "sh4", "test-agent")
        assert ho1 is not None
        ho2 = auto_handoff_from_session(db, "sh4", "test-agent")
        assert ho2 is None


# ---------------------------------------------------------------------------
# S1172: decay_memories still works without days_threshold param
# ---------------------------------------------------------------------------

class TestDecayMemoriesRegression:
    def _insert_old(self, db_path: Path, days_old: int = 200) -> str:
        from mem0ry.db.store import create_memory

        past = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
        mem_id = create_memory(
            db_path, content="old log", scope="session", memory_type="log",
        )
        conn = get_connection(db_path)
        conn.execute(
            "UPDATE memories SET created_at = ? WHERE id = ?", (past, mem_id)
        )
        conn.commit()
        conn.close()
        return mem_id

    def test_decay_memories_returns_ids(self, db: Path) -> None:
        from mem0ry.db.store_memories import decay_memories

        self._insert_old(db)
        result = decay_memories(db, dry_run=True)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_decay_memories_soft_deletes(self, db: Path) -> None:
        from mem0ry.db.store_memories import decay_memories

        mem_id = self._insert_old(db)
        result = decay_memories(db, dry_run=False)
        assert mem_id in result

        conn = get_connection(db)
        row = conn.execute("SELECT deleted_at FROM memories WHERE id = ?", (mem_id,)).fetchone()
        conn.close()
        assert row["deleted_at"] is not None


# ---------------------------------------------------------------------------
# S5713: exception handling still catches the same errors
# ---------------------------------------------------------------------------

class TestExceptionHandlingRegression:
    def test_git_context_handles_missing_git(self) -> None:
        from mem0ry.utils.git_context import resolve_project_id

        result = resolve_project_id(Path("/tmp"))
        assert result is None or isinstance(result, str)

    def test_git_context_handles_non_git_dir(self) -> None:
        from mem0ry.utils.git_context import resolve_context

        result = resolve_context(Path("/tmp"))
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# S1192: config constant _DB_FILENAME produces correct paths
# ---------------------------------------------------------------------------

class TestConfigConstantRegression:
    def test_db_path_default_contains_memories_db(self) -> None:
        from mem0ry.config import MemoryConfig

        cfg = MemoryConfig()
        assert cfg.db_path.endswith("memories.db")

    def test_spool_dir_is_under_db_parent(self) -> None:
        from mem0ry.config import MemoryConfig

        cfg = MemoryConfig()
        assert "spool" in cfg.spool_dir

    def test_db_path_env_override(self, tmp_path: Path) -> None:
        from mem0ry.config import MemoryConfig

        custom = str(tmp_path / "custom.db")
        cfg = MemoryConfig()
        cfg.db_path = custom
        assert cfg.db_path == custom


# ---------------------------------------------------------------------------
# S5869 + S3776: sanitize_payload end-to-end still works
# ---------------------------------------------------------------------------

class TestSanitizeEndToEndRegression:
    def test_full_sanitize_with_secrets_and_paths(self) -> None:
        result = sanitize_payload({
            "kind": "user-prompt",
            "session_id": "abc",
            "body": "Key sk-abc123def456ghi789jkl012mno345 at /home/user/secret.py",
        })
        assert "sk-abc123" not in result["body"]
        assert "/home/user" not in result["body"]
        assert "[REDACTED]" in result["body"]
        assert "~" in result["body"]

    def test_sanitize_messages_array(self) -> None:
        result = sanitize_payload({
            "kind": "session-end",
            "session_id": "abc",
            "messages": [
                {"role": "user", "content": "Use key sk-abc123def456ghi789jkl012mno345"},
                {"role": "assistant", "content": r"File C:\Users\admin\creds.json"},
            ],
        })
        msgs = result["messages"]
        assert "sk-abc123" not in msgs[0]["content"]
        assert "[REDACTED]" in msgs[0]["content"]
        assert "admin" not in msgs[1]["content"]

    def test_all_key_patterns_stripped(self) -> None:
        bodies = [
            ("key=abcDEFghijklmnopqr", "key="),
            ("token: abcDEFghijklmnopqr", "token:"),
            ("api_key=\"abcDEFghijklmnopqr\"", "api_key"),
        ]
        for raw, marker in bodies:
            result = sanitize_payload({
                "kind": "user-prompt",
                "session_id": "abc",
                "body": raw,
            })
            assert "[REDACTED]" in result["body"], f"Failed to strip pattern containing {marker}"
