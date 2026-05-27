"""Vector store backed by sqlite-vec — zero external server dependency."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import sqlite_vec  # type: ignore[import-untyped]


class VectorStore:
    """Store and search document embeddings using sqlite-vec.

    Each document is identified by its relative path (string).
    A metadata table maps rowid -> path for human-readable results.

    Usage::

        store = VectorStore(Path("data/conversations/.vec.db"), dim=300)
        store.add("2025-01-01/topic.md", embedding, {"title": "Topic"})
        results = store.query(embedding, top_k=5)
    """

    def __init__(self, db_path: Path, dim: int = 300) -> None:
        self._db_path = db_path
        self._dim = dim
        self._conn = self._connect()
        self._create_table()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self._db_path))
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        return db

    def _create_table(self) -> None:
        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories "
            f"USING vec0(embedding float[{self._dim}])"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS metadata "
            "(rowid INTEGER PRIMARY KEY, path TEXT, title TEXT, source TEXT)"
        )
        self._conn.commit()

    def _path_to_rowid(self, path: str) -> int:
        return hash(path) & 0x7FFFFFFF

    def add(
        self,
        path: str,
        embedding: np.ndarray,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Insert or replace a vector for *path*."""
        rowid = self._path_to_rowid(path)
        vec_bytes = embedding.astype(np.float32).tobytes()
        self._conn.execute("DELETE FROM vec_memories WHERE rowid = ?", (rowid,))
        self._conn.execute(
            "INSERT INTO vec_memories(rowid, embedding) VALUES (?, ?)",
            (rowid, vec_bytes),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO metadata(rowid, path, title, source) VALUES (?, ?, ?, ?)",
            (
                rowid,
                path,
                (meta or {}).get("title", ""),
                (meta or {}).get("source", ""),
            ),
        )
        self._conn.commit()

    def query(self, embedding: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        """Return (path, distance) pairs sorted by cosine distance (ascending)."""
        vec_bytes = embedding.astype(np.float32).tobytes()
        rows = self._conn.execute(
            "SELECT m.path, v.distance "
            "FROM vec_memories v JOIN metadata m ON v.rowid = m.rowid "
            "WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
            (vec_bytes, top_k),
        ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def delete(self, path: str) -> None:
        """Remove a vector and its metadata by *path*."""
        rowid = self._path_to_rowid(path)
        self._conn.execute("DELETE FROM vec_memories WHERE rowid = ?", (rowid,))
        self._conn.execute("DELETE FROM metadata WHERE rowid = ?", (rowid,))
        self._conn.commit()

    def count(self) -> int:
        row = self._conn.execute("SELECT count(*) FROM metadata").fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> VectorStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
