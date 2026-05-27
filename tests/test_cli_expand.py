"""Regression tests for the CLI expand command formatting.

Catches the bug where score_fmt ('f' float format) was incorrectly applied
to the 'Score' header string — ValueError: Unknown format code 'f' for
object of type 'str'.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mem0ry.cli.main import app

runner = CliRunner()


def _mock_expander(scores: list[tuple[str, float]]) -> MagicMock:
    expander = MagicMock()
    expander.similar_tokens.return_value = scores
    return expander


@patch("mem0ry.cli.main._get_expander")
def test_expand_small_scores_formats_correctly(mock_get: MagicMock) -> None:
    """Scores < 10 must render with 4 decimal places, no crash."""
    mock_get.return_value = _mock_expander(
        [
            ("paris", 0.6321),
            ("french", 0.5123),
        ]
    )

    result = runner.invoke(app, ["expand", "france"])
    assert result.exit_code == 0, result.output
    assert "paris" in result.output
    assert "french" in result.output
    assert "0.6321" in result.output


@patch("mem0ry.cli.main._get_expander")
def test_expand_large_scores_formats_correctly(mock_get: MagicMock) -> None:
    """Scores >= 10 must widen the column, no crash."""
    mock_get.return_value = _mock_expander(
        [
            ("paris", 15.3),
            ("french", 12.8),
        ]
    )

    result = runner.invoke(app, ["expand", "france"])
    assert result.exit_code == 0, result.output
    assert "15.3000" in result.output


@patch("mem0ry.cli.main._get_expander")
def test_expand_negative_scores(mock_get: MagicMock) -> None:
    """Negative scores (from spaCy filtering) must not crash formatting."""
    mock_get.return_value = _mock_expander(
        [
            ("tok1", -2.0),
            ("tok2", -1.5),
        ]
    )

    result = runner.invoke(app, ["expand", "test"])
    assert result.exit_code == 0, result.output


@patch("mem0ry.cli.main._get_expander")
def test_expand_single_result(mock_get: MagicMock) -> None:
    """Single result must not crash max() on a one-element list."""
    mock_get.return_value = _mock_expander(
        [
            ("lonely", 0.42),
        ]
    )

    result = runner.invoke(app, ["expand", "test"])
    assert result.exit_code == 0, result.output
    assert "lonely" in result.output


@patch("mem0ry.cli.main._get_expander")
def test_expand_no_results(mock_get: MagicMock) -> None:
    """Empty results must print 'Nenhum token similar encontrado'."""
    mock_get.return_value = _mock_expander([])

    result = runner.invoke(app, ["expand", "xyz"])
    assert result.exit_code == 0, result.output
    assert "Nenhum token similar encontrado" in result.output
