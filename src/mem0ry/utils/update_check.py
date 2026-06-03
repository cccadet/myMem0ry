"""Check PyPI for newer versions of myMem0ry and print a one-line warning."""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error

from mem0ry.config import _DATA_DIR

_PACKAGE = "mymem0ry"
_CACHE_FILE = _DATA_DIR / ".pypi_version_cache.json"
_CACHE_TTL = 86400  # 24 hours


def _installed_version() -> str:
    try:
        from importlib.metadata import version as _v
        return _v(_PACKAGE)
    except Exception:
        return "0.0.0"


def _fetch_latest() -> str | None:
    url = f"https://pypi.org/pypi/{_PACKAGE}/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data["info"]["version"]
    except Exception:
        return None


def _read_cache() -> str | None:
    if not _CACHE_FILE.exists():
        return None
    try:
        cached = json.loads(_CACHE_FILE.read_text())
        if time.time() - cached.get("ts", 0) < _CACHE_TTL:
            return cached.get("version")
    except Exception:
        pass
    return None


def _write_cache(version: str) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps({"version": version, "ts": time.time()}))
    except Exception:
        pass


def check_for_update() -> None:
    installed = _installed_version()
    cached = _read_cache()
    latest: str | None = cached
    if latest is None:
        latest = _fetch_latest()
        if latest is not None:
            _write_cache(latest)
    if latest is None:
        return
    def _parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split(".")[:3])

    if _parse(latest) <= _parse(installed):
        return
    typer = __import__("typer")
    typer.echo(
        typer.style(
            f"  myMem0ry {latest} is available (you have {installed}). "
            f"Run: uv tool upgrade myMem0ry",
            fg=typer.colors.YELLOW,
        )
    )
