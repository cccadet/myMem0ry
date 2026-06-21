"""Nomic embed text encoder using ONNX Runtime.

This module avoids pulling in ``sentence-transformers``/``torch`` by running the
official Nomic ONNX weights directly with ``onnxruntime``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import onnxruntime as ort
from huggingface_hub import snapshot_download
from tokenizers import Tokenizer

logger = logging.getLogger(__name__)

DEFAULT_REPO_ID = "nomic-ai/nomic-embed-text-v1.5"
_ONNX_FILE_QUANTIZED = "onnx/model_quantized.onnx"
_ONNX_FILE_FULL = "onnx/model.onnx"
_TOKENIZER_FILES = [
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "config.json",
]


def _default_cache_dir(repo_id: str) -> Path:
    """Return a deterministic cache directory under ``~/.cache/mymem0ry``."""
    return Path.home() / ".cache" / "mymem0ry" / repo_id.split("/")[-1]


class NomicOnnxEncoder:
    """Encoder for ``nomic-embed-text-v1.5`` using ONNX Runtime.

    Downloads the tokenizer and ONNX weights from HuggingFace on first use and
    caches them under ``~/.cache/mymem0ry/nomic-embed-text-v1.5``. Falls back
    from the quantized model to the full ONNX model if the quantized file is
    missing.

    Output vectors are 768-dimensional, mean-pooled over the last hidden state
    and L2-normalized, matching the upstream Nomic sentence-transformers
    implementation.

    Usage::

        encoder = NomicOnnxEncoder()
        vec = encoder.encode("Python programming language")
        assert vec.shape == (768,)
        assert vec.dtype == np.float32
    """

    def __init__(
        self,
        repo_id: str = DEFAULT_REPO_ID,
        cache_dir: Path | None = None,
        use_quantized: bool = True,
    ) -> None:
        self._repo_id = repo_id
        self._cache_dir = cache_dir or _default_cache_dir(repo_id)
        self._model_dir = self._download_files()
        self._tokenizer = self._load_tokenizer()
        self._session = self._load_session(use_quantized=use_quantized)
        self._dim = 768

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, text: str) -> np.ndarray:
        """Return a (768,) float32 vector for *text*."""
        matrix = self.encode_batch([text])
        return matrix[0]

    def encode_batch(self, texts: Sequence[str]) -> np.ndarray:
        """Return an (N, 768) float32 matrix. One row per text."""
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)

        encoded = self._tokenizer.encode_batch(list(texts), add_special_tokens=True)
        max_len = max(len(e.ids) for e in encoded)

        input_ids = np.zeros((len(encoded), max_len), dtype=np.int64)
        attention_mask = np.zeros((len(encoded), max_len), dtype=np.int64)
        for i, enc in enumerate(encoded):
            length = len(enc.ids)
            input_ids[i, :length] = enc.ids
            attention_mask[i, :length] = 1

        outputs = self._session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": np.zeros_like(input_ids),
            },
        )
        last_hidden = outputs[0]
        return self._mean_pool(last_hidden, attention_mask)

    def _download_files(self) -> Path:
        """Download tokenizer + ONNX weights and return the local directory."""
        allow_patterns = [_ONNX_FILE_QUANTIZED, _ONNX_FILE_FULL] + _TOKENIZER_FILES
        local_dir = snapshot_download(
            repo_id=self._repo_id,
            cache_dir=self._cache_dir,
            local_dir=self._cache_dir,
            allow_patterns=allow_patterns,
        )
        return Path(local_dir)

    def _load_tokenizer(self) -> Tokenizer:
        """Load the HuggingFace fast tokenizer from the cached model directory."""
        path = self._model_dir / "tokenizer.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Tokenizer not found at {path}. "
                f"Try deleting {self._cache_dir} and retrying."
            )
        return Tokenizer.from_file(str(path))

    def _load_session(self, use_quantized: bool) -> ort.InferenceSession:
        """Load the ONNX model, preferring the quantized variant when requested."""
        candidates: list[str] = []
        if use_quantized:
            candidates.append(_ONNX_FILE_QUANTIZED)
        candidates.append(_ONNX_FILE_FULL)

        for name in candidates:
            path = self._model_dir / name
            if path.exists():
                logger.debug("Loading ONNX model from %s", path)
                return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

        raise FileNotFoundError(
            f"No ONNX model found in {self._model_dir / 'onnx'}. "
            f"Try deleting {self._cache_dir} and retrying."
        )

    @staticmethod
    def _mean_pool(last_hidden: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        """Mean-pool the last hidden state using the attention mask and L2-normalize."""
        mask = attention_mask[..., None].astype(np.float32)
        summed = (last_hidden * mask).sum(axis=1)
        counts = np.maximum(mask.sum(axis=1), 1e-9)
        pooled = summed / counts
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        normalized = pooled / np.maximum(norms, 1e-9)
        return normalized.astype(np.float32)
