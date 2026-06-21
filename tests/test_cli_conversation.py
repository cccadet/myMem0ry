"""Tests for cli.conversation commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mem0ry.cli.main import app

runner = CliRunner()


@patch("mem0ry.conversations.encoders.get_encoder")
@patch("mem0ry.conversations.vector_store.VectorStore")
def test_build_vector_index_with_files(
    mock_store_cls: MagicMock, mock_get_encoder: MagicMock, tmp_path: Path
) -> None:
    from mem0ry.cli.conversation import _build_vector_index
    from mem0ry.config import MemoryConfig

    cfg = MemoryConfig()
    (tmp_path / "a.md").write_text("hello world", encoding="utf-8")
    (tmp_path / "empty.md").write_text("   ", encoding="utf-8")

    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = [0.1] * cfg.embedding_dim
    mock_encoder.dim = cfg.embedding_dim
    mock_get_encoder.return_value = mock_encoder
    mock_store = MagicMock()
    mock_store_cls.return_value = mock_store

    _build_vector_index(tmp_path, cfg)

    assert mock_store.add.call_count == 1
    mock_store.close.assert_called_once()


@patch("mem0ry.conversations.encoders.get_encoder")
@patch("mem0ry.conversations.vector_store.VectorStore")
def test_build_vector_index_no_files(
    mock_store_cls: MagicMock, _mock_get_encoder: MagicMock, tmp_path: Path
) -> None:
    from mem0ry.cli.conversation import _build_vector_index
    from mem0ry.config import MemoryConfig

    cfg = MemoryConfig()
    mock_store = MagicMock()
    mock_store_cls.return_value = mock_store

    _build_vector_index(tmp_path, cfg)

    mock_store.add.assert_not_called()
    mock_store.close.assert_called_once()


@patch("mem0ry.cli.conversation.SpacyConceptSearch")
def test_get_expander(mock_cs: MagicMock, tmp_path: Path) -> None:
    from mem0ry.cli.conversation import _get_expander
    from mem0ry.config import MemoryConfig

    cfg = MemoryConfig()
    _get_expander(cfg)
    mock_cs.assert_called_once_with(model_name=cfg.spacy_model)


@patch("mem0ry.cli.conversation.split_conversations")
def test_split_with_explicit_source(
    mock_split: MagicMock, tmp_path: Path
) -> None:
    source = tmp_path / "export"
    source.mkdir()
    mock_split.return_value = {"written": 2, "skipped": 1}

    result = runner.invoke(
        app, ["split", "--source", str(source), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 0
    assert "Total: 2 files written, 1 skipped" in result.output


@patch("mem0ry.cli.conversation.split_conversations")
def test_split_skips_invalid_source(
    mock_split: MagicMock, tmp_path: Path
) -> None:
    source = tmp_path / "bad"
    source.mkdir()
    mock_split.side_effect = ValueError("unsupported")

    result = runner.invoke(
        app, ["split", "--source", str(source), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 0
    assert "Total: 0 files written, 0 skipped" in result.output


@patch("mem0ry.conversations.spacy_expand.expand_query_spacy", return_value="expanded python")
@patch("mem0ry.cli.conversation._get_expander")
def test_search_with_expand(
    mock_get_expander: MagicMock,
    mock_expand: MagicMock,
    tmp_path: Path,
) -> None:
    (tmp_path / "test.md").write_text("python", encoding="utf-8")
    with patch("mem0ry.conversations.search.search", return_value=[]):
        result = runner.invoke(
            app,
            [
                "search",
                "python",
                "--conversations",
                str(tmp_path),
                "--expand",
            ],
        )
    assert result.exit_code == 0
    assert "Query expandida" in result.output


@patch("mem0ry.conversations.encoders.get_encoder")
@patch("mem0ry.conversations.vector_store.VectorStore")
@patch("mem0ry.conversations.search_hybrid.search_hybrid")
def test_search_hybrid_backend(
    mock_hybrid: MagicMock,
    mock_store_cls: MagicMock,
    mock_get_encoder: MagicMock,
    tmp_path: Path,
) -> None:
    (tmp_path / "test.md").write_text("python", encoding="utf-8")
    mock_hybrid.return_value = [tmp_path / "test.md"]
    mock_store = MagicMock()
    mock_store_cls.return_value = mock_store
    mock_encoder = MagicMock()
    mock_encoder.dim = 768
    mock_get_encoder.return_value = mock_encoder

    result = runner.invoke(
        app,
        [
            "search",
            "python",
            "--conversations",
            str(tmp_path),
            "--backend",
            "hybrid",
        ],
    )
    assert result.exit_code == 0
    assert "hybrid" in result.output
    mock_store.close.assert_called_once()


def test_search_unknown_backend(tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("python", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "search",
            "python",
            "--conversations",
            str(tmp_path),
            "--backend",
            "magic",
        ],
    )
    assert result.exit_code == 1
    assert "Unknown backend" in result.output


@patch("mem0ry.conversations.benchmark.run_benchmark")
@patch("mem0ry.conversations.spacy_expand.expand_query_spacy", return_value="expanded")
@patch("mem0ry.cli.conversation._get_expander")
def test_benchmark_with_expand(
    _mock_get_expander: MagicMock,
    _mock_expand: MagicMock,
    mock_bench: MagicMock,
    tmp_path: Path,
) -> None:
    (tmp_path / "test.md").write_text("python", encoding="utf-8")
    mock_bench.return_value = [
        {
            "backend": "ripgrep",
            "time_ms": 10.0,
            "n_files": 1,
            "paths": [Path("test.md")],
        },
    ]
    result = runner.invoke(
        app,
        [
            "benchmark",
            "python",
            "--conversations",
            str(tmp_path),
            "--expand",
        ],
    )
    assert result.exit_code == 0
    assert "Query: expanded" in result.output


@patch("mem0ry.cli.conversation.SpacyConceptSearch")
def test_expand_no_results(mock_cs: MagicMock) -> None:
    mock_cs.return_value.similar_tokens.return_value = []
    result = runner.invoke(app, ["expand", "xyz"])
    assert result.exit_code == 0
    assert "Nenhum token similar" in result.output


@patch("mem0ry.cli.conversation.SpacyConceptSearch")
def test_expand_with_results(mock_cs: MagicMock) -> None:
    mock_cs.return_value.similar_tokens.return_value = [
        ("python", 0.9),
        ("java", -0.5),
    ]
    result = runner.invoke(app, ["expand", "programming"])
    assert result.exit_code == 0
    assert "python" in result.output
    assert "0.9000" in result.output


@patch("mem0ry.cli.conversation.build_bm25_index")
def test_index_unknown_backend(mock_bm25: MagicMock, tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("content", encoding="utf-8")
    result = runner.invoke(
        app, ["index", "--backend", "magic", "--conversations", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert "Unknown backend" in result.output
    mock_bm25.assert_not_called()
