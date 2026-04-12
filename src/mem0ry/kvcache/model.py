"""Model loading, KV cache building, and chat generation."""

from __future__ import annotations

import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from ..config import MemoryConfig
from .cache import load_kv, save_kv


def _get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _get_dtype(device: str) -> torch.dtype:
    if device == "cuda":
        return torch.float16
    if device == "mps":
        return torch.float16
    return torch.float32


def load_model(config: MemoryConfig | None = None):
    config = config or MemoryConfig()
    device = _get_device()
    dtype = _get_dtype(device)

    print(f"[memoria] Carregando {config.kvcache_model} em {device}...")
    tokenizer = AutoTokenizer.from_pretrained(config.kvcache_model)
    model = AutoModelForCausalLM.from_pretrained(
        config.kvcache_model,
        torch_dtype=dtype,
        device_map=device,
    )
    model.eval()
    return model, tokenizer, device, dtype


def build_cache(
    memories_text: str,
    config: MemoryConfig | None = None,
    model=None,
    tokenizer=None,
) -> int:
    config = config or MemoryConfig()

    if model is None or tokenizer is None:
        model, tokenizer, device, _ = load_model(config)
    else:
        device = next(model.parameters()).device

    cache_path = Path(config.kvcache_path)
    meta_path = Path(config.kvcache_meta_path)

    prompt = (
        "<|im_start|>system\n"
        "Você é um assistente pessoal. As informações abaixo são memórias do usuário. "
        "Use-as para responder perguntas sobre ele.\n\n"
        f"{memories_text.strip()}\n"
        "<|im_end|>\n"
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=config.kvcache_max_tokens,
    ).to(device)

    n_tokens = inputs["input_ids"].shape[1]

    if n_tokens >= config.kvcache_max_tokens:
        print(f"[aviso] Memórias truncadas para {config.kvcache_max_tokens} tokens.")

    print(f"[memoria] Processando {n_tokens} tokens de memória...")

    with torch.no_grad():
        out = model(**inputs, use_cache=True)

    save_kv(out.past_key_values, cache_path)

    meta = {
        "model": config.kvcache_model,
        "n_tokens": n_tokens,
        "prompt_preview": prompt[:200],
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    size_mb = cache_path.stat().st_size / 1e6
    print(f"[memoria] Cache salvo em {cache_path} ({size_mb:.1f} MB)")
    return n_tokens


def chat(
    question: str,
    config: MemoryConfig | None = None,
    model=None,
    tokenizer=None,
) -> str:
    config = config or MemoryConfig()

    cache_path = Path(config.kvcache_path)
    meta_path = Path(config.kvcache_meta_path)

    if not cache_path.exists():
        raise FileNotFoundError(
            "Cache não encontrado. Rode primeiro: mymem0ry build-cache"
        )

    if model is None or tokenizer is None:
        model, tokenizer, device, dtype = load_model(config)
    else:
        device = next(model.parameters()).device
        dtype = next(model.parameters()).dtype

    past_key_values = load_kv(cache_path, device, dtype)
    meta = json.loads(meta_path.read_text())
    n_mem_tokens = meta["n_tokens"]

    question_prompt = f"<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n"

    inputs = tokenizer(question_prompt, return_tensors="pt").to(device)
    input_ids = inputs["input_ids"]
    n_q_tokens = input_ids.shape[1]

    position_ids = torch.arange(
        n_mem_tokens,
        n_mem_tokens + n_q_tokens,
        dtype=torch.long,
        device=device,
    ).unsqueeze(0)

    with torch.no_grad():
        output_ids = model.generate(
            input_ids=input_ids,
            past_key_values=past_key_values,
            position_ids=position_ids,
            max_new_tokens=config.chat_max_new_tokens,
            use_cache=True,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )

    new_tokens = output_ids[0][n_q_tokens:]
    response = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return response.strip()
