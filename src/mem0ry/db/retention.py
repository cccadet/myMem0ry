"""Retention logic — salience scoring, soft/hard delete, pin/unpin, forget sweep.

Retention tier is derived from memory_type (no separate column):

    memory_type  → tier          → behaviour
    ────────────────────────────────────────────────
    log          → working       → 30-90 day decay
    pattern      → procedural    → frequency-based decay
    fact         → semantic      → indefinite (pinned by default)
    decision     → semantic      → indefinite (pinned by default)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .connection import get_connection
from .schema import init_schema


_TIER_MAP: dict[str, str] = {
    "log": "working",
    "pattern": "procedural",
    "fact": "semantic",
    "decision": "semantic",
}

_TIER_MAX_DAYS: dict[str, int] = {
    "working": 90,
    "procedural": 365,
    "semantic": 36500,
}

_SALIENCE_LAMBDA = 0.005
_SALIENCE_SIGMA = 0.3
_SALIENCE_MU = 0.01
_GRACE_DAYS = 7
_SALIENCE_THRESHOLD = 0.15


def tier_from_type(memory_type: str) -> str:
    return _TIER_MAP.get(memory_type, "working")


def compute_salience(
    memory_type: str,
    created_at: str,
    access_count: int,
    last_accessed_at: str | None,
) -> float:
    now = datetime.now(timezone.utc)
    try:
        created = datetime.fromisoformat(created_at)
    except (ValueError, TypeError):
        return 0.5

    days_old = max(0.0, (now - created).total_seconds() / 86400)

    base = 0.5 if memory_type in ("fact", "decision") else 0.3

    time_decay = base * math.exp(-_SALIENCE_LAMBDA * days_old)

    if last_accessed_at:
        try:
            last_acc = datetime.fromisoformat(last_accessed_at)
            days_since = max(0.0, (now - last_acc).total_seconds() / 86400)
        except (ValueError, TypeError):
            days_since = days_old
    else:
        days_since = days_old

    freq_bonus = _SALIENCE_SIGMA * math.log1p(access_count) * math.exp(
        -_SALIENCE_MU * days_since
    )

    return round(time_decay + freq_bonus, 6)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def pin_memory(db_path: Path, memory_id: str) -> bool:
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        cursor = conn.execute(
            "UPDATE memories SET pinned = 1 WHERE id = ? AND deleted_at IS NULL",
            (memory_id,),
        )
        conn.commit()
        affected = cursor.rowcount
    finally:
        conn.close()
    return affected > 0


def unpin_memory(db_path: Path, memory_id: str) -> bool:
    conn = get_connection(db_path)
    try:
        init_schema(conn)
        cursor = conn.execute(
            "UPDATE memories SET pinned = 0 WHERE id = ?", (memory_id,)
        )
        conn.commit()
        affected = cursor.rowcount
    finally:
        conn.close()
    return affected > 0


def forget_sweep(
    db_path: Path, dry_run: bool = False
) -> dict[str, Any]:
    conn = get_connection(db_path)
    try:
        init_schema(conn)

        hard_delete_ids: list[str] = []
        for row in conn.execute(
            "SELECT id FROM memories WHERE deleted_at IS NOT NULL AND grace_until < ?",
            (_now_iso(),),
        ).fetchall():
            hard_delete_ids.append(row["id"])

        if not dry_run and hard_delete_ids:
            placeholders = ",".join("?" for _ in hard_delete_ids)
            conn.execute(
                f"DELETE FROM memories WHERE id IN ({placeholders})",
                hard_delete_ids,
            )
            conn.commit()

        candidates = conn.execute(
            "SELECT id, memory_type, created_at, access_count, last_accessed_at, "
            "pinned, deleted_at, salience FROM memories WHERE deleted_at IS NULL AND pinned = 0"
        ).fetchall()

        to_soft_delete: list[dict[str, Any]] = []
        now = _now_iso()
        grace = (
            datetime.now(timezone.utc) + timedelta(days=_GRACE_DAYS)
        ).isoformat()

        for row in candidates:
            mem = dict(row)
            tier = tier_from_type(mem["memory_type"])
            max_days = _TIER_MAX_DAYS.get(tier, 90)

            try:
                created = datetime.fromisoformat(mem["created_at"])
                days_old = (datetime.now(timezone.utc) - created).total_seconds() / 86400
            except (ValueError, TypeError):
                continue

            if days_old < max_days:
                continue

            salience = compute_salience(
                mem["memory_type"],
                mem["created_at"],
                mem["access_count"],
                mem["last_accessed_at"],
            )

            if salience < _SALIENCE_THRESHOLD:
                to_soft_delete.append(
                    {
                        "id": mem["id"],
                        "memory_type": mem["memory_type"],
                        "tier": tier,
                        "salience": salience,
                        "days_old": round(days_old, 1),
                    }
                )

                if not dry_run:
                    conn.execute(
                        "UPDATE memories SET deleted_at = ?, grace_until = ?, salience = ? WHERE id = ?",
                        (now, grace, salience, mem["id"]),
                    )

        if not dry_run and to_soft_delete:
            conn.commit()
    finally:
        conn.close()

    return {
        "soft_deleted": to_soft_delete,
        "hard_deleted": hard_delete_ids,
        "soft_count": len(to_soft_delete),
        "hard_count": len(hard_delete_ids),
    }


def update_salience_for_all(db_path: Path) -> int:
    conn = get_connection(db_path)
    try:
        init_schema(conn)

        rows = conn.execute(
            "SELECT id, memory_type, created_at, access_count, last_accessed_at FROM memories "
            "WHERE deleted_at IS NULL"
        ).fetchall()

        updated = 0
        for row in rows:
            s = compute_salience(
                row["memory_type"],
                row["created_at"],
                row["access_count"],
                row["last_accessed_at"],
            )
            conn.execute("UPDATE memories SET salience = ? WHERE id = ?", (s, row["id"]))
            updated += 1

        conn.commit()
    finally:
        conn.close()
    return updated
