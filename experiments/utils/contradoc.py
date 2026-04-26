"""ContraDoc-specific gold pair resolution."""

from .text import fuzzy_match_sentence, similarity


def resolve_gold_sentence(target_text: str, tagged_sentence, sentences) -> tuple[int | None, str]:
    """Two-stage resolution for the gold (evidence / reference) sentence.

    1. Prefer the LLM's tagged sentence if its source_text is similar enough
       to the target.
    2. Otherwise fall back to fuzzy matching the target against all sentences.

    Returns (sentence_id or None, resolution_tag) where resolution_tag
    explains which branch fired: 'llm_tag' / 'fuzzy_recovered' /
    'fuzzy_override_bad_tag' / 'unmatched'.
    """
    if tagged_sentence is not None:
        sim = similarity(tagged_sentence.source_text, target_text)
        if sim >= 0.85:
            return tagged_sentence.sentence_id, "llm_tag"
    sid, _ = fuzzy_match_sentence(target_text, sentences)
    if sid is not None:
        tag = "fuzzy_recovered" if tagged_sentence is None else "fuzzy_override_bad_tag"
        return sid, tag
    return None, "unmatched"
