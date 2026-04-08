"""Dataset tooling for building and analyzing ChatML exports."""

from .builder import build_chatml_examples
from .dedupe import deduplicate_examples
from .filter import apply_quality_filters
from .qa_cache import QACache, QACacheEntry, load_cache, save_cache
from .qa_generator import QAPair, generate_qa_pairs, qa_pairs_to_chatml
from .splitter import train_val_split
from .stats import compute_stats
from .temporal import build_temporal_system_prompt, enrich_conversations

__all__ = [
    "build_chatml_examples",
    "apply_quality_filters",
    "deduplicate_examples",
    "train_val_split",
    "compute_stats",
    "build_temporal_system_prompt",
    "enrich_conversations",
    "QACache",
    "QACacheEntry",
    "load_cache",
    "save_cache",
    "QAPair",
    "generate_qa_pairs",
    "qa_pairs_to_chatml",
]
