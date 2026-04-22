"""Tests for pipeline.dataset — _write_jsonl and _write_json helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from mem0ry.pipeline.dataset import _write_jsonl, _write_json


def test_write_jsonl_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "train.jsonl"
    examples = [{"a": 1}, {"b": 2}]
    _write_jsonl(examples, out)
    assert out.exists()
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"a": 1}


def test_write_jsonl_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "dir" / "data.jsonl"
    _write_jsonl([], out)
    assert out.exists()


def test_write_json_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "stats.json"
    payload = {"total": 10, "avg": 5.0}
    _write_json(payload, out)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["total"] == 10


def test_write_json_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "path" / "out.json"
    _write_json({"key": "val"}, out)
    assert out.exists()


def test_write_jsonl_empty_list(tmp_path: Path) -> None:
    out = tmp_path / "empty.jsonl"
    _write_jsonl([], out)
    assert out.exists()
    assert out.read_text(encoding="utf-8") == ""
