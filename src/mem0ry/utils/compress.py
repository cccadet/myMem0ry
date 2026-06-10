"""Optional SmartCrusher integration for get_context results.

Requires: headroom-ai[code] (uv sync --extra compress)
Enable: MEM0RY_COMPRESS=1
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_HAS_SMART_CRUSHER = False
try:
    from headroom import SmartCrusher, SmartCrusherConfig
    from headroom.config import CCRConfig
    _HAS_SMART_CRUSHER = True
except ImportError:
    pass


def compress_memory_array(
    memories: list[dict[str, Any]], query: str = ""
) -> list[dict[str, Any]]:
    """Compress memory array using SmartCrusher if enabled and available.

    Args:
        memories: List of memory dicts from get_context
        query: Optional query for relevance scoring

    Returns:
        Original or compressed memories (fail-safe: original on any error)
    """
    if not _HAS_SMART_CRUSHER:
        return memories

    if os.environ.get("MEM0RY_COMPRESS", "0") != "1":
        return memories

    if not memories:
        return memories

    try:
        json_str = json.dumps(memories, ensure_ascii=False)
        tokens_before = len(json_str) // 4

        config = SmartCrusherConfig(
            min_tokens_to_crush=200,
            max_items_after_crush=15,
            factor_out_constants=False,
        )
        ccr_config = CCRConfig(enabled=False, inject_retrieval_marker=False)
        crusher = SmartCrusher(config=config, ccr_config=ccr_config)

        result = crusher.crush(json_str, query=query)

        if not result.was_modified:
            return memories

        compressed_memories = json.loads(result.compressed)

        if os.environ.get("MEM0RY_COMPRESS_LOG", "0") == "1":
            tokens_after = len(result.compressed) // 4
            logger.info(
                "SmartCrusher: tokens_before=%d tokens_after=%d was_modified=%s",
                tokens_before,
                tokens_after,
                result.was_modified,
            )

        return compressed_memories

    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        logger.debug("SmartCrusher compression failed, returning original: %s", e)
        return memories
    except Exception as e:
        logger.debug("SmartCrusher unexpected error, returning original: %s", e)
        return memories
