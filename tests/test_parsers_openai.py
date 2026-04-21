"""Tests for parsers.openai — ChatGPT export parsing."""

from __future__ import annotations

import json
from pathlib import Path

from mem0ry.parsers.openai import OpenAIParser


def _make_mapping(nodes: list[dict]) -> dict:
    return {n["id"]: n for n in nodes}


def test_parse_simple_conversation(tmp_path: Path) -> None:
    mapping = _make_mapping([
        {
            "id": "root",
            "children": ["c1"],
        },
        {
            "id": "c1",
            "message": {
                "author": {"role": "user"},
                "content": {"parts": ["Hello"]},
                "id": "m1",
            },
            "children": ["c2"],
        },
        {
            "id": "c2",
            "message": {
                "author": {"role": "assistant"},
                "content": {"parts": ["Hi there"]},
                "id": "m2",
            },
            "children": [],
        },
    ])
    payload = [{"id": "conv1", "title": "Test", "create_time": "1700000000.0", "mapping": mapping}]
    path = tmp_path / "export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    parser = OpenAIParser()
    convs = parser.parse(path)
    assert len(convs) == 1
    assert convs[0].title == "Test"
    assert len(convs[0].messages) == 2
    assert convs[0].messages[0].role == "user"
    assert convs[0].messages[0].content == "Hello"
    assert convs[0].messages[1].role == "assistant"


def test_parse_skips_empty_mapping(tmp_path: Path) -> None:
    payload = [{"id": "conv2", "title": "Empty", "mapping": {}}]
    path = tmp_path / "export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    parser = OpenAIParser()
    assert parser.parse(path) == []


def test_parse_skips_system_roles(tmp_path: Path) -> None:
    mapping = _make_mapping([
        {"id": "root", "children": ["c1"]},
        {
            "id": "c1",
            "message": {
                "author": {"role": "system"},
                "content": {"parts": ["System msg"]},
            },
            "children": [],
        },
    ])
    payload = [{"id": "conv3", "mapping": mapping}]
    path = tmp_path / "export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    parser = OpenAIParser()
    convs = parser.parse(path)
    assert len(convs) == 0


def test_parse_list_format(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text(json.dumps([]), encoding="utf-8")

    parser = OpenAIParser()
    assert parser.parse(path) == []
