"""Tests for conversations.spacy_expand — expand_query_spacy and SpacyConceptSearch helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from mem0ry.conversations.spacy_expand import expand_query_spacy, SpacyConceptSearch


class FakeSpacyConceptSearch:
    """Lightweight fake that doesn't require loading the real spaCy model."""

    def __init__(self, results: list[tuple[str, float]] | None = None) -> None:
        self._results = results or []

    def similar_tokens(self, text: str, top_k: int = 10) -> list[tuple[str, float]]:
        return self._results


def test_expand_query_appends_similar_tokens() -> None:
    fake = FakeSpacyConceptSearch([("programação", 0.8), ("código", 0.6)])
    result = expand_query_spacy("python", fake, top_k=5)
    assert result.startswith("python")
    assert "programação" in result
    assert "código" in result


def test_expand_query_no_results_returns_original() -> None:
    fake = FakeSpacyConceptSearch([])
    result = expand_query_spacy("python", fake)
    assert result == "python"


def test_expand_query_deduplicates() -> None:
    fake = FakeSpacyConceptSearch([("python", 0.9), ("Python", 0.8)])
    result = expand_query_spacy("python", fake)
    tokens = result.split()
    lower_tokens = [t.lower() for t in tokens]
    assert lower_tokens.count("python") == 1


def test_expand_query_filters_single_char() -> None:
    fake = FakeSpacyConceptSearch([("x", 0.5), ("código", 0.7)])
    result = expand_query_spacy("python", fake)
    assert " x " not in result
    assert "código" in result


def test_expand_query_excludes_tokens_in_query() -> None:
    fake = FakeSpacyConceptSearch([("python", 0.9), ("snake", 0.5)])
    result = expand_query_spacy("python", fake)
    tokens = result.split()[1:]
    assert "python" not in tokens


def test_select_unique_top_k() -> None:
    sims = np.array([0.1, 0.9, 0.8, 0.1, 0.7], dtype=np.float32)
    words = np.array(["alpha", "beta", "gamma", "alpha", "delta"])

    fake = MagicMock(spec=SpacyConceptSearch)
    fake._vocab_words = words
    result = SpacyConceptSearch._select_unique_top_k(fake, sims, 3)
    assert len(result) == 3
    tokens = [t for t, _ in result]
    assert "beta" in tokens
    assert "gamma" in tokens
    assert len(set(tokens)) == len(tokens)


def test_mask_query_variants_zeros_self() -> None:
    sims = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    words = np.array(["python", "programação", "código"])

    class FakeDoc:
        text = "python"

    class FakeToken:
        def __init__(self, text: str) -> None:
            self.text = text

    doc = MagicMock()
    doc.__iter__ = lambda self_iter: iter([FakeToken("python")])

    fake_search = MagicMock(spec=SpacyConceptSearch)
    fake_search._vocab_words = words
    SpacyConceptSearch._mask_query_variants(fake_search, sims, doc)
    assert sims[0] == -2.0
