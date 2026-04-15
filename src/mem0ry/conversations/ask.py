"""Search conversations and answer using on-the-fly generation."""

from __future__ import annotations

from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from ..config import MemoryConfig
from .search import search
from .search_bm25 import search_bm25
from .search_fts import search_fts

_BACKENDS = {
    "ripgrep": search,
    "bm25": search_bm25,
    "fts5": search_fts,
}


def _load_conversation_content(paths: list[Path], max_chars: int = 12000) -> str:
    """Load and concatenate conversation files up to max_chars."""
    parts: list[str] = []
    total = 0

    for path in paths:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if total + len(content) > max_chars:
            remaining = max_chars - total
            if remaining > 200:
                parts.append(content[:remaining] + "\n[...truncado]")
            break
        parts.append(content)
        total += len(content)

    return "\n\n---\n\n".join(parts)


def load_ask_model(config: MemoryConfig | None = None):
    """Load model and tokenizer once for reuse across multiple ask calls."""
    config = config or MemoryConfig()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device != "cpu" else torch.float32

    print(f"[memoria] Carregando {config.kvcache_model} em {device}...")
    tokenizer = AutoTokenizer.from_pretrained(config.kvcache_model)
    model = AutoModelForCausalLM.from_pretrained(
        config.kvcache_model,
        torch_dtype=dtype,
        device_map=device,
    )
    model.eval()
    return model, tokenizer, device


def ask(
    question: str,
    *,
    conversations_dir: Path,
    top_k: int = 3,
    backend: str = "ripgrep",
    config: MemoryConfig | None = None,
    model=None,
    tokenizer=None,
    device: str | None = None,
) -> str:
    """Search for relevant conversations and answer using the model directly.

    Instead of pre-building a KV cache, this builds the full prompt
    (context + question) and generates in a single pass.

    Args:
        question: User's question.
        conversations_dir: Directory with date-organized .md conversation files.
        top_k: Number of conversation files to retrieve.
        config: Optional configuration override.
        model: Pre-loaded model (avoids reload if provided).
        tokenizer: Pre-loaded tokenizer (avoids reload if provided).
        device: Device string (inferred from model if not provided).

    Returns:
        Model's answer string.
    """
    config = config or MemoryConfig()

    # 1. Search for relevant conversations
    search_fn = _BACKENDS.get(backend, search)
    paths = search_fn(question, conversations_dir, top_k=top_k)

    if not paths:
        return "Nenhuma conversa relevante encontrada."

    # 2. Load conversation content
    context = _load_conversation_content(paths)

    if not context.strip():
        return "Conversas encontradas, mas sem conteúdo para processar."

    # 3. Load model if not provided
    if model is None or tokenizer is None:
        model, tokenizer, device = load_ask_model(config)
    elif device is None:
        device = next(model.parameters()).device

    # 4. Build prompt and generate in a single pass
    prompt = (
        "<|im_start|>system\n"
        "Você é um assistente pessoal. As informações abaixo são memórias do usuário "
        "extraídas de conversas anteriores. Use-as para responder perguntas sobre ele.\n\n"
        f"{context.strip()}\n"
        "<|im_end|>\n"
        f"<|im_start|>user\n{question}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=config.kvcache_max_tokens,
    ).to(device)

    n_tokens = inputs["input_ids"].shape[1]
    print(f"[memoria] Gerando resposta com {n_tokens} tokens de contexto...")

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=config.chat_max_new_tokens,
            use_cache=True,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    new_tokens = output_ids[0][n_tokens:]
    response = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return response.strip()
