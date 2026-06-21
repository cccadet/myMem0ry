"""Tests for conversations.encoders — factory and ONNX encoder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from mem0ry.conversations.encoders import (
    NomicOnnxEncoder,
    SpacyEncoder,
    VALID_ENCODER_BACKENDS,
    get_encoder,
)
from mem0ry.conversations.encoders.nomic_onnx import DEFAULT_REPO_ID
from mem0ry.config import MemoryConfig


@pytest.fixture
def mock_nlp():
    fake_nlp = MagicMock()
    fake_doc = MagicMock()
    fake_doc.vector = np.random.default_rng(42).random(300, dtype=np.float32)
    fake_nlp.return_value = fake_doc
    fake_nlp.pipe.return_value = iter([fake_doc, fake_doc])
    fake_nlp.vocab.vectors.shape = (500000, 300)
    return fake_nlp


def test_get_encoder_spacy(mock_nlp) -> None:
    with patch("mem0ry.conversations.encoders.spacy.spacy.load", return_value=mock_nlp):
        cfg = MemoryConfig()
        cfg.vector_encoder_model = "spacy"
        encoder = get_encoder(cfg)
        assert isinstance(encoder, SpacyEncoder)
        assert encoder.dim == 300


def test_get_encoder_nomic() -> None:
    with patch(
        "mem0ry.conversations.encoders.factory.NomicOnnxEncoder"
    ) as mock_cls:
        mock_encoder = MagicMock()
        mock_encoder.dim = 768
        mock_cls.return_value = mock_encoder
        cfg = MemoryConfig()
        cfg.vector_encoder_model = "nomic"
        encoder = get_encoder(cfg)
        assert encoder is mock_encoder
        mock_cls.assert_called_once_with()


def test_get_encoder_unknown() -> None:
    cfg = MemoryConfig()
    cfg.vector_encoder_model = "magic"
    with pytest.raises(ValueError, match="Unknown vector encoder backend"):
        get_encoder(cfg)


def test_valid_encoder_backends() -> None:
    assert VALID_ENCODER_BACKENDS == {"spacy", "nomic"}


def test_nomic_onnx_encoder_properties() -> None:
    encoder = NomicOnnxEncoder.__new__(NomicOnnxEncoder)
    encoder._dim = 768
    assert encoder.dim == 768


def test_nomic_onnx_encoder_encode_and_batch(tmp_path: Path) -> None:
    encoder = NomicOnnxEncoder.__new__(NomicOnnxEncoder)
    encoder._dim = 768

    fake_tokenizer = MagicMock()
    enc_a = MagicMock()
    enc_a.ids = [1, 2, 3]
    enc_b = MagicMock()
    enc_b.ids = [4, 5]
    fake_tokenizer.encode_batch.return_value = [enc_a, enc_b]
    encoder._tokenizer = fake_tokenizer

    fake_session = MagicMock()
    fake_last_hidden = np.zeros((2, 3, 768), dtype=np.float32)
    fake_last_hidden[0, 0, :] = 1.0
    fake_last_hidden[1, 0, :] = 2.0
    fake_session.run.return_value = [fake_last_hidden]
    encoder._session = fake_session

    result = encoder.encode_batch(["hello", "world"])
    assert result.shape == (2, 768)
    assert result.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(result, axis=1), 1.0, rtol=1e-5)

    single = encoder.encode("hello")
    assert single.shape == (768,)


def test_nomic_onnx_encoder_empty_batch() -> None:
    encoder = NomicOnnxEncoder.__new__(NomicOnnxEncoder)
    encoder._dim = 768
    result = encoder.encode_batch([])
    assert result.shape == (0, 768)


def test_nomic_onnx_download_uses_default_repo_id() -> None:
    with patch("mem0ry.conversations.encoders.nomic_onnx.snapshot_download") as mock_dl:
        mock_dl.return_value = str(Path.home() / "fake")
        encoder = NomicOnnxEncoder.__new__(NomicOnnxEncoder)
        encoder._repo_id = DEFAULT_REPO_ID
        encoder._cache_dir = Path.home() / ".cache" / "mymem0ry" / "nomic-embed-text-v1.5"
        encoder._download_files()
        mock_dl.assert_called_once()
        assert mock_dl.call_args.kwargs.get("repo_id") == DEFAULT_REPO_ID
