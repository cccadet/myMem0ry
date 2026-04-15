"""SQLite FTS5 search backend."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .search import _extract_keywords


def _db_path(conversations_dir: Path) -> Path:
    return conversations_dir / ".fts5_index.db"


def build_fts_index(conversations_dir: Path) -> None:
    """Build and save FTS5 index from all .md files in conversations_dir."""
    db_path = _db_path(conversations_dir)

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("DROP TABLE IF EXISTS conversations")
        conn.execute(
            "CREATE VIRTUAL TABLE conversations USING fts5("
            "path, content, tokenize='unicode61')"
        )

        files = sorted(conversations_dir.rglob("*.md"))
        count = 0
        for f in files:
            content = f.read_text(encoding="utf-8")
            rel_path = str(f.relative_to(conversations_dir))
            conn.execute(
                "INSERT INTO conversations (path, content) VALUES (?, ?)",
                (rel_path, content),
            )
            count += 1

    print(f"[fts5] Índice criado: {count} arquivos em {db_path}")


def search_fts(
    query: str,
    conversations_dir: Path,
    top_k: int = 5,
) -> list[Path]:
    """Search conversations using SQLite FTS5.

    Builds index on-the-fly if not cached.
    """
    db_path = _db_path(conversations_dir)

    if not db_path.exists():
        build_fts_index(conversations_dir)

    keywords = _extract_keywords(query)
    if not keywords:
        return []

    # FTS5 MATCH with OR for multiple keywords
    fts_query = " OR ".join(f'"{kw}"' for kw in keywords)

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("INSERT INTO conversations(conversations) VALUES('optimize')")
        rows = conn.execute(
            "SELECT path FROM conversations WHERE conversations MATCH ? "
            "ORDER BY rank LIMIT ?",
            (fts_query, top_k),
        ).fetchall()

    return [conversations_dir / row[0] for row in rows]
