"""Tests for conversations.embeddings — SpacyEncoder with spaCy vectors."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from mem0ry.conversations.embeddings import SpacyEncoder


@pytest.fixture
def mock_nlp():
    fake_nlp = MagicMock()
    fake_doc = MagicMock()
    fake_doc.vector = np.random.default_rng(42).random(300, dtype=np.float32)
    fake_nlp.return_value = fake_doc
    fake_nlp.pipe.return_value = iter([fake_doc, fake_doc])
    fake_nlp.vocab.vectors.shape = (500000, 300)
    return fake_nlp


def test_encode_returns_correct_dim(mock_nlp) -> None:
    with patch("mem0ry.conversations.embeddings.spacy.load", return_value=mock_nlp):
        encoder = SpacyEncoder("fake_model")
        vec = encoder.encode("test text")
        assert vec.shape == (300,)
        assert vec.dtype == np.float32


def test_encode_empty_string_returns_zeros(mock_nlp) -> None:
    with patch("mem0ry.conversations.embeddings.spacy.load", return_value=mock_nlp):
        encoder = SpacyEncoder("fake_model")
        vec = encoder.encode("  ")
        assert vec.shape == (300,)
        assert np.all(vec == 0)


def test_encode_batch_returns_matrix(mock_nlp) -> None:
    with patch("mem0ry.conversations.embeddings.spacy.load", return_value=mock_nlp):
        encoder = SpacyEncoder("fake_model")
        mat = encoder.encode_batch(["text one", "text two"])
        assert mat.shape == (2, 300)
        assert mat.dtype == np.float32


def test_encode_batch_empty_returns_empty(mock_nlp) -> None:
    with patch("mem0ry.conversations.embeddings.spacy.load", return_value=mock_nlp):
        encoder = SpacyEncoder("fake_model")
        mat = encoder.encode_batch([])
        assert mat.shape == (0, 300)


def test_dim_property(mock_nlp) -> None:
    with patch("mem0ry.conversations.embeddings.spacy.load", return_value=mock_nlp):
        encoder = SpacyEncoder("fake_model")
        assert encoder.dim == 300
