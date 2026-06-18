from __future__ import annotations

import re
import unicodedata

_VALID_SCOPES = {"global", "project", "context", "session"}
_VALID_SOURCES = {"claude-code", "opencode", "codex", "manual", "import", "hook"}
_VALID_MEMORY_TYPES = {"fact", "decision", "pattern", "log"}

_NOT_SUPERSEDED = "(superseded_by IS NULL OR superseded_by = '')"

_NOT_SUPERSEDED_M = "(m.superseded_by IS NULL OR m.superseded_by = '')"

_NOT_DELETED_M = "m.deleted_at IS NULL"

_JOIN_AND = " AND "

_SCOPE_PRIORITY = ["session", "context", "project", "global"]

# Whitelisted ORDER BY clauses for search/listing. Keys are the only values a
# caller (e.g. the web UI) may pass for ``order_by``; the default preserves the
# historical "most relevant first" ordering used everywhere else.
_DEFAULT_ORDER_M = "m.pinned DESC, m.salience DESC, m.created_at DESC"
_ORDER_BY_M = {
    "recent": "m.created_at DESC",
    "oldest": "m.created_at ASC",
    "salience": "m.salience DESC, m.created_at DESC",
    "access": "m.access_count DESC, m.created_at DESC",
    "title": "m.title COLLATE NOCASE ASC, m.created_at DESC",
}

# Stop words (EN + PT) filtered from free-text queries so a natural-language
# question doesn't match every row on common glue words.
_STOP_WORDS = frozenset(
    "a an the of to in on at for and or but is are was were be been being this "
    "that these those it its as by with from "
    "o a os as um uma de do da dos das em no na nos nas e ou que para por com "
    "como qual quais onde quando".split()
)


_SUFFIXES_PT = frozenset(
    "acao cao mento acao acoes amente ismo ista iveis aveis "
    "ando endo indo aram eram iram asse esse isse ado edo ido "
    "aram erem irem aria eria iria".split()
)

_SUFFIXES_EN = frozenset(
    "ing tion sion ment ness ly ful less able ible ous ive "
    "ize ise ate ful ings tions sions ments nesses".split()
)

_ALL_SUFFIXES = _SUFFIXES_PT | _SUFFIXES_EN


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.category(c).startswith("M"))


def _stem_word(word: str) -> str:
    for suffix in _ALL_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _normalize(text: str) -> str:
    return _strip_accents(text.lower())


def _query_terms(query: str | None) -> list[str]:
    """Extract meaningful, normalized search terms from a free-text query."""
    if not query:
        return []
    words = re.findall(r"[\wáàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ]+", query.lower())
    terms: list[str] = []
    for w in words:
        if len(w) <= 1 or w in _STOP_WORDS:
            continue
        terms.append(_normalize(w))
    return terms


def _query_terms_raw(query: str | None) -> list[str]:
    """Extract raw (un-normalized) terms for UI highlighting."""
    if not query:
        return []
    words = re.findall(r"[\wáàãâéêíóôõúüçÁÀÃÂÉÊÍÓÔÕÚÜÇ]+", query.lower())
    return [w for w in words if len(w) > 1 and w not in _STOP_WORDS]


def _validate_scope(scope: str) -> str:
    if scope not in _VALID_SCOPES:
        raise ValueError(
            f"Invalid scope '{scope}'. Expected one of: {', '.join(sorted(_VALID_SCOPES))}"
        )
    return scope


def _validate_source(source: str) -> str:
    if source not in _VALID_SOURCES:
        raise ValueError(
            f"Invalid source '{source}'. Expected one of: {', '.join(sorted(_VALID_SOURCES))}"
        )
    return source


def _validate_memory_type(memory_type: str) -> str:
    if memory_type not in _VALID_MEMORY_TYPES:
        raise ValueError(
            f"Invalid memory_type '{memory_type}'. Expected one of: {', '.join(sorted(_VALID_MEMORY_TYPES))}"
        )
    return memory_type
