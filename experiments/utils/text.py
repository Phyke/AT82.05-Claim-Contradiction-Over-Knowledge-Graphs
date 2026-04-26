"""Text normalization and fuzzy sentence matching used across notebooks."""

import re
from difflib import SequenceMatcher


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip trailing sentence punctuation."""
    return re.sub(r"\s+", " ", text).strip().lower().rstrip(".!?\"'")


def similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio on normalized strings."""
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def fuzzy_match_sentence(target: str, sentences, threshold: float = 0.85) -> tuple[int | None, float]:
    """Find sentence_id whose source_text best matches target.

    Returns (sentence_id or None, score). An exact-normalized match returns
    score 1.0; otherwise the best SequenceMatcher ratio across sentences,
    or (None, best_score) when nothing meets threshold.

    `sentences` is iterable of objects with .sentence_id and .source_text.
    """
    target_norm = normalize(target)
    for s in sentences:
        if normalize(s.source_text) == target_norm:
            return s.sentence_id, 1.0
    best_id, best_score = None, 0.0
    for s in sentences:
        score = SequenceMatcher(None, normalize(s.source_text), target_norm).ratio()
        if score > best_score:
            best_id, best_score = s.sentence_id, score
    return (best_id if best_score >= threshold else None), best_score
