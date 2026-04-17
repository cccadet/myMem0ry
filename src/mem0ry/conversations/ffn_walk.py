"""FFN walk — LARQL-inspired knowledge extraction from FFN layers.

Extracts gate/up projections and pre-computes feature-to-token mappings from a
model's feed-forward network layers.  At query time, computes GeGLU activations
(silu(gate) * up) to find activated features and looks up pre-computed tokens.

Cache layout (data/.cache/ffn/<model>/):
    gate_projs.pt        {layer_idx: Tensor(intermediate, hidden)}  (f16)
    up_projs.pt          {layer_idx: Tensor(intermediate, hidden)}  (f16)
    feature_tokens.pt    {layer_idx: (token_ids, scores)}           (int32 + f16)
    config.json          {model_name, layers, hidden_size, top_n, embed_scale}
"""

from __future__ import annotations

import json
from pathlib import Path

import torch

from .search import _STOP_WORDS

_CACHE_ROOT = Path("data/.cache/ffn")

# Default "knowledge band" — middle-to-late layers hold semantic knowledge
_DEFAULT_LAYER_RANGE = range(20, 36)

# Top-N tokens to pre-compute per feature during warmup
_FEATURE_TOP_N = 10

# Top-K features to activate per layer during query
_GATE_TOP_K = 32


def _cache_dir(model_name: str) -> Path:
    safe = model_name.replace("/", "--")
    return _CACHE_ROOT / safe


def _word_like(token_str: str) -> bool:
    """Check if a decoded token looks like a real word (3+ alpha chars)."""
    stripped = token_str.strip()
    if len(stripped) < 3:
        return False
    return stripped.isalpha()


def build_ffn_cache(
    model_name: str,
    layer_range: range | None = None,
    top_n: int = _FEATURE_TOP_N,
) -> Path:
    """Build the FFN walk cache: gate projections + feature-to-token lookup tables.

    Returns the cache directory path.
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer

    layer_range = layer_range or _DEFAULT_LAYER_RANGE

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    model.eval()

    # Navigate to the language model layers (handles Gemma4's nested structure)
    layers = _get_transformer_layers(model)
    lm_head = _get_lm_head(model)
    embed_tokens = _get_embed_tokens(model)

    hidden_size = embed_tokens.weight.shape[1]
    num_layers_total = len(layers)

    cache = _cache_dir(model_name)
    cache.mkdir(parents=True, exist_ok=True)

    # Detect embed_scale — only Gemma models scale embeddings by sqrt(hidden_size)
    model_type = getattr(model.config, "model_type", "")
    if model_type and model_type.startswith("gemma"):
        embed_scale = float(hidden_size**0.5)
    else:
        embed_scale = 1.0

    cache_config = {
        "model_name": model_name,
        "layers": list(layer_range),
        "hidden_size": hidden_size,
        "top_n": top_n,
        "embed_scale": embed_scale,
    }
    (cache / "config.json").write_text(json.dumps(cache_config, indent=2), encoding="utf-8")

    # Save tokenizer for query encoding
    tokenizer.backend_tokenizer.save(str(cache / "tokenizer.json"))

    # Save embeddings for query encoding
    embeddings = embed_tokens.weight.detach().to(torch.float16)
    torch.save(embeddings, cache / "embeddings.pt")

    # Process each layer
    gate_projs: dict[int, torch.Tensor] = {}
    up_projs: dict[int, torch.Tensor] = {}
    feature_tokens: dict[int, tuple[torch.Tensor, torch.Tensor]] = {}

    lm_head_f = lm_head.weight.detach().float()

    for li in layer_range:
        if li >= num_layers_total:
            continue
        mlp = layers[li].mlp

        # gate_proj: (intermediate, hidden) — save in f16
        gate_w = mlp.gate_proj.weight.detach().to(torch.float16)
        gate_projs[li] = gate_w
        layer_intermediate = gate_w.shape[0]

        # up_proj: (intermediate, hidden) — save in f16 (needed for GeGLU at query time)
        up_w = mlp.up_proj.weight.detach().to(torch.float16)
        up_projs[li] = up_w

        # down_proj: (hidden, intermediate)
        down_w = mlp.down_proj.weight.detach().float()  # (hidden, intermediate)

        # Pre-compute lm_head @ down_proj in chunks along the intermediate dim
        feat_chunk = 2048
        top_ids = torch.zeros(top_n, layer_intermediate, dtype=torch.long)
        top_vals = torch.full((top_n, layer_intermediate), float("-inf"))

        for fs in range(0, layer_intermediate, feat_chunk):
            fe = min(fs + feat_chunk, layer_intermediate)
            # lm_head: (vocab, hidden) @ down_w[:, fs:fe]: (hidden, chunk) → (vocab, chunk)
            logits_chunk = lm_head_f @ down_w[:, fs:fe]
            topv, topi = torch.topk(logits_chunk, top_n, dim=0)
            top_ids[:, fs:fe] = topi
            top_vals[:, fs:fe] = topv
            del logits_chunk, topv, topi

        del down_w

        feature_tokens[li] = (
            top_ids.to(torch.int32),
            top_vals.to(torch.float16),
        )

        print(f"  Layer {li}: gate/up_proj saved, {top_n} top-tokens per feature computed")

    torch.save(gate_projs, cache / "gate_projs.pt")
    torch.save(up_projs, cache / "up_projs.pt")
    torch.save(feature_tokens, cache / "feature_tokens.pt")

    del model
    return cache


def _get_transformer_layers(model):
    """Navigate different model architectures to find the transformer layers."""
    if hasattr(model, "model") and hasattr(model.model, "language_model"):
        # Gemma4: model.model.language_model.layers
        return model.model.language_model.layers
    if hasattr(model, "model") and hasattr(model.model, "layers"):
        # Standard: model.model.layers
        return model.model.layers
    raise ValueError(f"Cannot find transformer layers in {type(model).__name__}")


def _get_lm_head(model):
    """Get the language model head (output projection)."""
    if hasattr(model, "lm_head"):
        return model.lm_head
    raise ValueError(f"Cannot find lm_head in {type(model).__name__}")


def _get_embed_tokens(model):
    """Get the token embedding layer."""
    if hasattr(model, "model") and hasattr(model.model, "language_model"):
        return model.model.language_model.embed_tokens
    if hasattr(model, "model") and hasattr(model.model, "embed_tokens"):
        return model.model.embed_tokens
    raise ValueError(f"Cannot find embed_tokens in {type(model).__name__}")


class FFNCache:
    """Load and query a pre-built FFN walk cache."""

    def __init__(self, model_name: str) -> None:
        cache = _cache_dir(model_name)
        if not (cache / "gate_projs.pt").exists():
            raise FileNotFoundError(
                f"FFN cache not found for {model_name}. Run `mymem0ry warmup` first."
            )

        from tokenizers import Tokenizer

        self._tokenizer = Tokenizer.from_file(str(cache / "tokenizer.json"))
        self._embeddings = torch.load(cache / "embeddings.pt", weights_only=True).float()

        # Load embed_scale from config (Gemma uses sqrt(hidden_size))
        cfg = json.loads((cache / "config.json").read_text(encoding="utf-8"))
        self._embed_scale = cfg.get("embed_scale", 1.0)
        self._gate_projs: dict[int, torch.Tensor] = torch.load(
            cache / "gate_projs.pt", weights_only=True
        )
        # Load up_proj weights for GeGLU activation (silu(gate) * up)
        up_path = cache / "up_projs.pt"
        if up_path.exists():
            self._up_projs: dict[int, torch.Tensor] = torch.load(up_path, weights_only=True)
        else:
            self._up_projs = {}
        raw_ft = torch.load(cache / "feature_tokens.pt", weights_only=True)
        # Saved shape is (top_n, intermediate) — transpose to (intermediate, top_n)
        self._ft_ids: dict[int, torch.Tensor] = {k: v[0].T.long() for k, v in raw_ft.items()}
        self._ft_scores: dict[int, torch.Tensor] = {k: v[1].T.float() for k, v in raw_ft.items()}
        self._layers = sorted(self._gate_projs.keys())

    def _best_token_ids(self, text: str) -> list[int]:
        """Find the tokenization with fewest tokens for each word.

        BPE tokenizers (Llama, Qwen) may split lowercase words into subwords
        ("france" → ["fr", "ance"]) while the capitalized form is a single
        token ("France" → ["France"]). Fewer tokens give a stronger concept
        signal in the embedding space.
        """
        words = text.split()
        if len(words) <= 1:
            # Single word: try original vs capitalized
            ids_orig = self._tokenizer.encode(text).ids
            ids_cap = self._tokenizer.encode(text.capitalize()).ids
            return ids_orig if len(ids_orig) <= len(ids_cap) else ids_cap

        # Multi-word: try to optimize each word individually
        best_ids: list[int] = []
        for word in words:
            ids_orig = self._tokenizer.encode(word).ids
            ids_cap = self._tokenizer.encode(word.capitalize()).ids
            best_ids.extend(ids_orig if len(ids_orig) <= len(ids_cap) else ids_cap)
        return best_ids

    def describe(
        self, text: str, top_k: int = 10, gate_k: int = _GATE_TOP_K,
        debug: bool = False,
    ) -> list[tuple[str, float, int]]:
        """Find semantically related tokens via FFN walk.

        Returns list of (token, score, layer) sorted by score descending.

        Uses GeGLU activation (silu(gate) * up) when up_proj is available,
        which correctly amplifies semantic features over morphological ones.
        Falls back to raw gate scores for old caches without up_proj.
        """
        import torch.nn.functional as F

        # Encode query → pick tokenization with fewest tokens (best signal)
        # BPE tokenizers like Llama's split "france" → ["fr", "ance"] (2 tokens)
        # while "France" stays as 1 token. Fewer tokens = stronger concept signal.
        token_ids = self._best_token_ids(text)
        ids_tensor = torch.tensor(token_ids)
        query_vec = self._embeddings[ids_tensor].mean(dim=0)  # (hidden,)
        query_vec = query_vec * self._embed_scale

        # Normalize to post-RMSNorm scale — gate_proj expects input at residual stream
        # magnitude (~sqrt(hidden_size)), not raw embedding magnitude.
        # Gemma's embed_scale already handles this; other models need explicit normalization.
        hidden_size = query_vec.shape[0]
        query_vec = query_vec / query_vec.norm() * (hidden_size ** 0.5)

        has_up = bool(self._up_projs)

        if debug:
            print(f"  [debug] token_ids={token_ids}")
            print(f"  [debug] query_vec norm={query_vec.norm().item():.4f}")
            print(f"  [debug] using GeGLU: {has_up}")

        # Walk through cached layers
        candidates: list[tuple[str, float, int]] = []

        for li in self._layers:
            gate_proj = self._gate_projs[li].float()  # (intermediate, hidden)
            ft_ids = self._ft_ids[li]  # (intermediate, top_n)
            ft_scores = self._ft_scores[li]  # (intermediate, top_n)

            # Compute gate and (optionally) up projections
            gate_scores = gate_proj @ query_vec  # (intermediate,)

            if has_up and li in self._up_projs:
                up_proj = self._up_projs[li].float()  # (intermediate, hidden)
                up_scores = up_proj @ query_vec  # (intermediate,)
                # GeGLU activation: silu(gate) * up
                activations = F.silu(gate_scores) * up_scores
            else:
                # Fallback: raw gate scores (no GeGLU)
                activations = gate_scores

            if debug:
                top_debug = torch.topk(activations.abs(), min(5, activations.shape[0]))
                print(f"  [debug] L{li} top-5 activations: {[f'{v.item():.4f}' for v in top_debug.values]}")
                for fi in top_debug.indices[:3]:
                    top_tok = self._tokenizer.decode([ft_ids[fi][0].item()]).strip()
                    print(f"    feat {fi.item()}: act={activations[fi].item():.4f}, top_tok='{top_tok}' (score={ft_scores[fi][0].item():.2f})")

            # Select top-K features by activation magnitude
            topk = torch.topk(activations.abs(), min(gate_k, activations.shape[0]))

            for feat_idx in topk.indices:
                act_score = activations[feat_idx]
                # Lookup pre-computed top tokens for this feature
                ids = ft_ids[feat_idx]  # (top_n,)
                scores = ft_scores[feat_idx]  # (top_n,)

                for tok_id, tok_score in zip(ids, scores):
                    token_str = self._tokenizer.decode([tok_id.item()]).strip()
                    if not token_str or not _word_like(token_str):
                        continue
                    if token_str.lower() in _STOP_WORDS:
                        continue
                    # Combine activation × feature token logit contribution
                    combined = act_score.item() * tok_score.item()
                    candidates.append((token_str, combined, li))

        if not candidates:
            return []

        # Deduplicate: keep highest score per token
        best: dict[str, tuple[float, int]] = {}
        for token, score, layer in candidates:
            t_lower = token.lower()
            if t_lower not in best or score > best[t_lower][0]:
                best[t_lower] = (score, layer)

        # Sort by score descending
        results = [(tok, sc, ly) for tok, (sc, ly) in best.items()]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
