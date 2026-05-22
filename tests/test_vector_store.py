"""Tests for conversations.vector_store — sqlite-vec backed VectorStore."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mem0ry.conversations.vector_store import VectorStore


@pytest.fixture
def store(tmp_path: Path) -> VectorStore:
    db = tmp_path / "test_vec.db"
    return VectorStore(db, dim=8)


def _make_vec(values: list[float]) -> np.ndarray:
    return np.array(values, dtype=np.float32)


def test_add_and_query(store: VectorStore) -> None:
    vec_a = _make_vec([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    vec_b = _make_vec([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    store.add("a.md", vec_a)
    store.add("b.md", vec_b)

    query = _make_vec([0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    results = store.query(query, top_k=2)
    assert len(results) == 2
    assert results[0][0] == "a.md"


def test_count(store: VectorStore) -> None:
    assert store.count() == 0
    store.add("a.md", _make_vec([1.0] * 8))
    assert store.count() == 1
    store.add("b.md", _make_vec([0.5] * 8))
    assert store.count() == 2


def test_delete(store: VectorStore) -> None:
    store.add("a.md", _make_vec([1.0] * 8))
    assert store.count() == 1
    store.delete("a.md")
    assert store.count() == 0


def test_add_replaces(store: VectorStore) -> None:
    store.add("a.md", _make_vec([1.0] * 8))
    store.add("a.md", _make_vec([0.0] * 8))
    assert store.count() == 1


def test_query_empty(store: VectorStore) -> None:
    query = _make_vec([1.0] * 8)
    results = store.query(query, top_k=5)
    assert results == []


def test_close_and_context_manager(tmp_path: Path) -> None:
    db = tmp_path / "ctx.db"
    with VectorStore(db, dim=4) as store:
        store.add("x.md", _make_vec([1.0, 0.0, 0.0, 0.0]))
        assert store.count() == 1


def test_persistence(tmp_path: Path) -> None:
    db = tmp_path / "persist.db"
    vec = _make_vec([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    store1 = VectorStore(db, dim=8)
    store1.add("persist.md", vec)
    store1.close()

    store2 = VectorStore(db, dim=8)
    assert store2.count() == 1
    results = store2.query(vec, top_k=1)
    assert results[0][0] == "persist.md"
    store2.close()
