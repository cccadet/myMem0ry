"""Tests for PyPI version check utilities."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mem0ry.utils import update_check


def test_installed_version_returns_installed_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_check, "_PACKAGE", "pip")
    version = update_check._installed_version()
    # pip is guaranteed to be installed in the test environment.
    assert version.count(".") >= 1


def test_installed_version_fallback() -> None:
    with patch.object(update_check, "_PACKAGE", "definitely-not-a-package-12345"):
        assert update_check._installed_version() == "0.0.0"


def test_fetch_latest_parses_response() -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"info": {"version": "9.9.9"}}).encode()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        assert update_check._fetch_latest() == "9.9.9"


def test_fetch_latest_returns_none_on_error() -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("no network")):
        assert update_check._fetch_latest() is None


def test_read_cache_returns_none_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_check, "_CACHE_FILE", tmp_path / "cache.json")
    assert update_check._read_cache() is None


def test_read_cache_returns_fresh_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps({"version": "1.2.3", "ts": time.time()}))
    monkeypatch.setattr(update_check, "_CACHE_FILE", cache_file)
    assert update_check._read_cache() == "1.2.3"


def test_read_cache_returns_none_when_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps({"version": "1.2.3", "ts": time.time() - 999999}))
    monkeypatch.setattr(update_check, "_CACHE_FILE", cache_file)
    assert update_check._read_cache() is None


def test_write_cache_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_file = tmp_path / "cache.json"
    monkeypatch.setattr(update_check, "_CACHE_FILE", cache_file)
    update_check._write_cache("2.0.0")
    data = json.loads(cache_file.read_text())
    assert data["version"] == "2.0.0"
    assert "ts" in data


def test_check_for_update_prints_warning_when_newer(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(update_check, "_PACKAGE", "mymem0ry")
    monkeypatch.setattr(update_check, "_CACHE_FILE", tmp_path / "cache.json")

    with (
        patch.object(update_check, "_installed_version", return_value="0.0.1"),
        patch.object(update_check, "_fetch_latest", return_value="9.9.9"),
    ):
        update_check.check_for_update()

    captured = capsys.readouterr()
    assert "9.9.9" in captured.out
    assert "0.0.1" in captured.out


def test_check_for_update_silent_when_up_to_date(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(update_check, "_PACKAGE", "mymem0ry")
    monkeypatch.setattr(update_check, "_CACHE_FILE", tmp_path / "cache.json")

    with (
        patch.object(update_check, "_installed_version", return_value="9.9.9"),
        patch.object(update_check, "_fetch_latest", return_value="9.9.9"),
    ):
        update_check.check_for_update()

    captured = capsys.readouterr()
    assert captured.out == ""


def test_check_for_update_silent_when_fetch_fails(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(update_check, "_CACHE_FILE", tmp_path / "cache.json")

    with patch.object(update_check, "_fetch_latest", return_value=None):
        update_check.check_for_update()

    captured = capsys.readouterr()
    assert captured.out == ""
