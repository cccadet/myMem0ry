"""SQLite/DoltLite connection factory for the memories database."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import sqlite_vec  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_DOLTLITE_AVAILABLE: bool | None = None


def _is_doltlite_available() -> bool:
    """Return whether the DoltLite Python binding can be imported."""
    global _DOLTLITE_AVAILABLE
    if _DOLTLITE_AVAILABLE is None:
        try:
            import doltlite  # type: ignore[import-not-found]  # noqa: F401

            _DOLTLITE_AVAILABLE = True
        except Exception:
            _DOLTLITE_AVAILABLE = False
    return _DOLTLITE_AVAILABLE


def _use_doltlite_for_path(db_path: Path) -> bool:
    """Decide whether to open the database with the DoltLite engine."""
    if not _is_doltlite_available():
        return False
    # If a plain SQLite database already exists, keep using SQLite unless the
    # user explicitly asked for DoltLite. This avoids accidentally converting
    # an existing database just because doltlite happens to be installed.
    if db_path.exists():
        return _is_doltlite_db_file(db_path)
    # New database and DoltLite is installed: create it as DoltLite if requested.
    return _doltlite_enabled_via_env()


def _doltlite_enabled_via_env() -> bool:
    """Return True when the user explicitly enabled DoltLite for new DBs."""
    import os

    return os.environ.get("MEM0RY_SYNC_ENGINE", "auto").lower() == "doltlite"


def _is_doltlite_db_file(db_path: Path) -> bool:
    """Peek at a database file to detect whether it uses DoltLite."""
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        try:
            return is_doltlite_db(conn)
        finally:
            conn.close()
    except Exception:
        return False


def is_doltlite_db(conn: sqlite3.Connection) -> bool:
    """Detect whether a connection uses the DoltLite engine."""
    try:
        result = conn.execute("SELECT doltlite_engine()").fetchone()
        return result is not None and result[0] == "prolly"
    except sqlite3.OperationalError:
        return False


def _load_sqlite_vec(conn: sqlite3.Connection) -> None:
    """Load the sqlite-vec extension, with a DoltLite-compatible fallback."""
    conn.enable_load_extension(True)
    load_error: Exception | None = None
    try:
        sqlite_vec.load(conn)
        return
    except Exception as exc:
        if not is_doltlite_db(conn):
            raise
        load_error = exc
        logger.debug("sqlite_vec.load failed on DoltLite: %s", exc)

    # DoltLite cannot always resolve the extension through the importlib path
    # used by sqlite_vec.load. Fall back to loading the .so directly.
    vec_path = Path(sqlite_vec.__file__).parent / "vec0.so"
    if not vec_path.exists():
        candidates = list(Path(sqlite_vec.__file__).parent.glob("*.so"))
        if candidates:
            vec_path = candidates[0]
    if not vec_path.exists():
        raise RuntimeError("sqlite-vec extension not found") from load_error

    conn.load_extension(str(vec_path))
    conn.enable_load_extension(False)


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite or DoltLite connection with sqlite-vec loaded.

    Creates parent directories if needed. The connection uses WAL journal mode
    for concurrent read/write support when running on plain SQLite.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    use_doltlite = _use_doltlite_for_path(db_path)

    if use_doltlite:
        # Importing the DoltLite module bootstraps its sqlite3 extension hook.
        import doltlite  # type: ignore[import-not-found]  # noqa: F401

        logger.debug("Using DoltLite engine for %s", db_path)

    conn = sqlite3.connect(str(db_path), timeout=15)
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")

    # WAL is a SQLite-native feature; DoltLite may not support it.
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        if is_doltlite_db(conn):
            logger.debug("WAL not supported by DoltLite engine")

    _load_sqlite_vec(conn)
    conn.row_factory = sqlite3.Row
    return conn
