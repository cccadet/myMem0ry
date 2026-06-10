"""Tests for SmartCrusher integration in get_context."""

from __future__ import annotations

import importlib
import json
import logging
from unittest.mock import MagicMock, patch


def test_noop_when_disabled(monkeypatch):
    """MEM0RY_COMPRESS=0 → input == output, no headroom call."""
    monkeypatch.setenv("MEM0RY_COMPRESS", "0")
    import mem0ry.utils.compress
    importlib.reload(mem0ry.utils.compress)
    from mem0ry.utils.compress import compress_memory_array

    memories = [{"id": "1", "content": "test"}]
    with patch.object(mem0ry.utils.compress, "_HAS_SMART_CRUSHER", True):
        with patch("mem0ry.utils.compress.SmartCrusher") as mock_crusher:
            result = compress_memory_array(memories)
            assert result == memories
            mock_crusher.assert_not_called()


def test_noop_when_headroom_missing(monkeypatch):
    """headroom not installed → no-op without raising ImportError."""
    import mem0ry.utils.compress
    with patch.object(mem0ry.utils.compress, "_HAS_SMART_CRUSHER", False):
        from mem0ry.utils.compress import compress_memory_array

        memories = [{"id": "1", "content": "test"}]
        result = compress_memory_array(memories)
        assert result == memories


def test_noop_when_not_modified(monkeypatch):
    """was_modified=False → input == output."""
    monkeypatch.setenv("MEM0RY_COMPRESS", "1")

    mock_result = MagicMock()
    mock_result.was_modified = False
    mock_result.compressed = '[{"id": "1"}]'

    import mem0ry.utils.compress
    importlib.reload(mem0ry.utils.compress)

    with patch.object(mem0ry.utils.compress, "_HAS_SMART_CRUSHER", True):
        with patch("mem0ry.utils.compress.SmartCrusher") as MockCrusher:
            instance = MockCrusher.return_value
            instance.crush.return_value = mock_result

            from mem0ry.utils.compress import compress_memory_array
            memories = [{"id": "1", "content": "test"}]
            result = compress_memory_array(memories)
            assert result == memories


def test_noop_on_invalid_json(monkeypatch):
    """Invalid JSON from crusher → input == output."""
    monkeypatch.setenv("MEM0RY_COMPRESS", "1")

    mock_result = MagicMock()
    mock_result.was_modified = True
    mock_result.compressed = "not valid json {"

    import mem0ry.utils.compress
    importlib.reload(mem0ry.utils.compress)

    with patch.object(mem0ry.utils.compress, "_HAS_SMART_CRUSHER", True):
        with patch("mem0ry.utils.compress.SmartCrusher") as MockCrusher:
            instance = MockCrusher.return_value
            instance.crush.return_value = mock_result

            from mem0ry.utils.compress import compress_memory_array
            memories = [{"id": "1", "content": "test"}]
            result = compress_memory_array(memories)
            assert result == memories


def test_compresses_when_modified(monkeypatch):
    """was_modified=True + valid JSON → output is compressed."""
    monkeypatch.setenv("MEM0RY_COMPRESS", "1")

    compressed_data = [{"id": "1"}]
    mock_result = MagicMock()
    mock_result.was_modified = True
    mock_result.compressed = json.dumps(compressed_data)

    import mem0ry.utils.compress
    importlib.reload(mem0ry.utils.compress)

    with patch.object(mem0ry.utils.compress, "_HAS_SMART_CRUSHER", True):
        with patch("mem0ry.utils.compress.SmartCrusher") as MockCrusher:
            instance = MockCrusher.return_value
            instance.crush.return_value = mock_result

            from mem0ry.utils.compress import compress_memory_array
            memories = [{"id": "1", "content": "test", "extra": "data"}]
            result = compress_memory_array(memories)
            assert result == compressed_data


def test_logs_metrics_when_logging_enabled(monkeypatch, caplog):
    """MEM0RY_COMPRESS_LOG=1 → logs tokens_before/tokens_after."""
    monkeypatch.setenv("MEM0RY_COMPRESS", "1")
    monkeypatch.setenv("MEM0RY_COMPRESS_LOG", "1")

    mock_result = MagicMock()
    mock_result.was_modified = True
    mock_result.compressed = '[{"id": "1"}]'

    import mem0ry.utils.compress
    importlib.reload(mem0ry.utils.compress)

    with patch.object(mem0ry.utils.compress, "_HAS_SMART_CRUSHER", True):
        with patch("mem0ry.utils.compress.SmartCrusher") as MockCrusher:
            instance = MockCrusher.return_value
            instance.crush.return_value = mock_result

            from mem0ry.utils.compress import compress_memory_array

            with caplog.at_level(logging.INFO):
                compress_memory_array([{"id": "1", "content": "test"}])

            assert any("tokens_before" in record.message for record in caplog.records)


def test_passthrough_when_no_memories(monkeypatch):
    """Empty list → []."""
    monkeypatch.setenv("MEM0RY_COMPRESS", "1")

    import mem0ry.utils.compress
    importlib.reload(mem0ry.utils.compress)

    with patch.object(mem0ry.utils.compress, "_HAS_SMART_CRUSHER", True):
        from mem0ry.utils.compress import compress_memory_array
        result = compress_memory_array([])
        assert result == []


def test_ccr_disabled_explicitly(monkeypatch):
    """CCRConfig.enabled=False is passed to SmartCrusher."""
    monkeypatch.setenv("MEM0RY_COMPRESS", "1")

    mock_result = MagicMock()
    mock_result.was_modified = False

    import mem0ry.utils.compress
    importlib.reload(mem0ry.utils.compress)

    with patch.object(mem0ry.utils.compress, "_HAS_SMART_CRUSHER", True):
        with patch("mem0ry.utils.compress.SmartCrusher") as MockCrusher, \
             patch("mem0ry.utils.compress.CCRConfig") as MockCCRConfig:
            instance = MockCrusher.return_value
            instance.crush.return_value = mock_result

            from mem0ry.utils.compress import compress_memory_array
            compress_memory_array([{"id": "1"}])

            MockCCRConfig.assert_called_once_with(
                enabled=False, inject_retrieval_marker=False
            )
            MockCrusher.assert_called_once()
            call_kwargs = MockCrusher.call_args[1]
            assert "ccr_config" in call_kwargs


def test_rust_extension_missing(monkeypatch):
    """headroom._core (Rust) missing → ImportError caught, no-op."""
    import mem0ry.utils.compress
    with patch.object(mem0ry.utils.compress, "_HAS_SMART_CRUSHER", False):
        from mem0ry.utils.compress import compress_memory_array

        memories = [{"id": "1", "content": "test"}]
        result = compress_memory_array(memories)
        assert result == memories
