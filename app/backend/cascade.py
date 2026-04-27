import hashlib
from collections.abc import AsyncIterator

import numpy as np
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from config import settings
from neo4j_store import Neo4jStore
from nli_scorer import NliScorer
from triples import extract_document
from vector import top_k_pairs


from typing import Literal


class VerifierVerdict(BaseModel):
    is_contradiction: bool = Field(description="True if the two sentences cannot both be true about the same subject. False otherwise. Decide this FIRST and INDEPENDENTLY of contradiction_type below.")
    explanation: str = Field(description="Brief explanation in 1-3 sentences naming the conflicting elements (or, if not a contradiction, why they are compatible).")
    contradiction_type: Literal["negation", "numerical", "antonymic", "factual", "structural", "other"] = Field(
        default="other",
        description=(
            "Best-fit label, INDEPENDENT of is_contradiction. 'other' is always acceptable, including for true contradictions that do not fit one of the specific labels. "
            "Do NOT downgrade is_contradiction to false just because no specific label fits - use 'other' instead."
        ),
    )


VERIFIER_PROMPT = """You are deciding whether two sentences from the SAME document logically contradict each other. Assume both sentences refer to the same entities, populations, and contexts unless the text clearly says otherwise.

Sentence A: {a}

Sentence B: {b}

A pair IS a contradiction if both sentences cannot simultaneously be true about the same subject. Mark is_contradiction=true in any of these cases:
- Negation flip: A asserts X, B asserts not-X.
- Numerical mismatch: A says ~70%, B says ~40% for the same statistic. Different numbers about the same fact ALWAYS count as a contradiction, even if framed as "surveys indicate".
- Antonymic: A and B use opposite adjectives or states about the same subject.
- Factual mismatch: different names, dates, places, or attributes for the same entity.
- Structural: same predicate but the argument roles are reversed or the cause/effect is flipped.

A pair is NOT a contradiction only when:
- A and B describe genuinely different entities/events/timeframes.
- B is a strictly more specific qualification of A and does not negate it.

Be assertive. If A and B make claims that cannot both hold for the same subject, return true. Do not return false just because the surface framing differs ("studies show" vs "surveys indicate") - that does not save the inconsistency.

Return:
- is_contradiction: true or false, applying the criteria above.
- explanation: 1-3 sentences justifying the verdict, naming the conflicting elements.
- contradiction_type: pick the best-fit label - one of negation, numerical, antonymic, factual, structural, other. 'other' is acceptable for any verdict.
"""


def _build_verifier(model: str):
    if model.startswith("claude-"):
        llm = ChatAnthropic(model=model, api_key=settings.anthropic_api_key, timeout=60)
    elif model.startswith("gpt-"):
        llm = ChatOpenAI(model=model, api_key=settings.openai_api_key, timeout=60)
    else:
        raise ValueError(f"Unrecognized verifier model: {model}")
    return llm.with_structured_output(VerifierVerdict)


def _doc_id(document: str) -> str:
    return hashlib.sha256(document.strip().encode("utf-8")).hexdigest()[:32]


async def _verify(verifier, a: str, b: str) -> VerifierVerdict | None:
    try:
        return await verifier.ainvoke(VERIFIER_PROMPT.format(a=a, b=b))
    except Exception as e:
        logger.warning("Verifier failed for pair: {}", e)
        return None


async def stream_cascade(
    document: str,
    verifier_model: str,
    store: Neo4jStore,
    nli_scorer: NliScorer,
    sbert: SentenceTransformer,
) -> AsyncIterator[dict]:
    doc_id = _doc_id(document)
    logger.info("Cascade run: doc_id={}, verifier={}", doc_id, verifier_model)
    yield {"event": "started", "doc_id": doc_id}

    if store.doc_exists(doc_id):
        meta = store.get_doc_meta(doc_id)
        yield {
            "event": "triples",
            "sentence_count": meta["n_chunks"],
            "triple_count": meta["n_triples"],
            "cached": True,
        }
        yield {"event": "ingested", "chunks": meta["n_chunks"], "cached": True}
    else:
        extraction = await extract_document(document)
        n_sentences = len(extraction.sentences)
        n_triples = sum(len(s.triples) for s in extraction.sentences)
        yield {
            "event": "triples",
            "sentence_count": n_sentences,
            "triple_count": n_triples,
            "cached": False,
        }

        texts = [s.source_text for s in extraction.sentences]
        if texts:
            embeddings = sbert.encode(
                texts,
                batch_size=64,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        else:
            embeddings = np.zeros((0, settings.embed_dim), dtype=np.float32)

        chunks_payload = []
        for sent, emb in zip(extraction.sentences, embeddings):
            chunks_payload.append({
                "sentence_id": sent.sentence_id,
                "source_text": sent.source_text,
                "embedding": emb.tolist(),
                "triples": [t.model_dump() for t in sent.triples],
            })

        preview = document.strip()[:200]
        result = store.ingest_document(doc_id, document, preview, chunks_payload)
        yield {"event": "ingested", "chunks": result["n_chunks"], "cached": False}

    chunks_data = store.get_chunks(doc_id)
    sid_to_text = {c["sentence_id"]: c["source_text"] for c in chunks_data}

    structural = store.structural_pairs(doc_id)
    structural_payload = [
        {"a_id": a, "b_id": b, "a_text": sid_to_text.get(a, ""), "b_text": sid_to_text.get(b, "")}
        for a, b in sorted(structural)
    ]
    yield {"event": "candidates", "stage": "structural", "pairs": structural_payload}

    if len(chunks_data) >= 2:
        sids = [c["sentence_id"] for c in chunks_data]
        emb_arr = np.array([c["embedding"] for c in chunks_data], dtype=np.float32)
        vector_raw = top_k_pairs(sids, emb_arr, settings.vector_top_k)
    else:
        vector_raw = []

    vector_set: set[tuple[int, int]] = set()
    vector_payload = []
    for a, b, score in vector_raw:
        a_norm, b_norm = sorted([a, b])
        vector_set.add((a_norm, b_norm))
        vector_payload.append({
            "a_id": a_norm,
            "b_id": b_norm,
            "a_text": sid_to_text.get(a_norm, ""),
            "b_text": sid_to_text.get(b_norm, ""),
            "score": score,
        })
    yield {"event": "candidates", "stage": "vector", "pairs": vector_payload}

    union = structural | vector_set
    union_sorted = sorted(union)
    union_payload = [
        {"a_id": a, "b_id": b, "a_text": sid_to_text.get(a, ""), "b_text": sid_to_text.get(b, "")}
        for a, b in union_sorted
    ]
    yield {"event": "candidates", "stage": "union", "pairs": union_payload}

    if not union_sorted:
        yield {"event": "nli_scored", "pairs_above_threshold": []}
        return

    pairs_for_nli = [(sid_to_text[a], sid_to_text[b]) for a, b in union_sorted]
    scores = nli_scorer.score_pairs(pairs_for_nli)

    above_threshold = []
    for (a, b), s in zip(union_sorted, scores):
        if s >= settings.nli_threshold:
            above_threshold.append({
                "a_id": a,
                "b_id": b,
                "a_text": sid_to_text[a],
                "b_text": sid_to_text[b],
                "nli_score": s,
            })
    above_threshold.sort(key=lambda p: -p["nli_score"])
    yield {"event": "nli_scored", "pairs_above_threshold": above_threshold}

    if not above_threshold:
        return

    verifier = _build_verifier(verifier_model)
    total = len(above_threshold)
    for idx, p in enumerate(above_threshold):
        verdict = await _verify(verifier, p["a_text"], p["b_text"])
        is_contra = bool(verdict and verdict.is_contradiction)
        explanation = verdict.explanation if verdict else None
        contra_type = verdict.contradiction_type if verdict else None
        if is_contra:
            yield {
                "event": "pair",
                "sentence_a": p["a_text"],
                "sentence_b": p["b_text"],
                "explanation": explanation,
                "contradiction_type": contra_type,
                "nli_score": p["nli_score"],
            }
        yield {
            "event": "verifier_step",
            "index": idx + 1,
            "total": total,
            "a_id": p["a_id"],
            "b_id": p["b_id"],
            "a_text": p["a_text"],
            "b_text": p["b_text"],
            "nli_score": p["nli_score"],
            "is_contradiction": is_contra,
            "explanation": explanation,
            "contradiction_type": contra_type,
            "failed": verdict is None,
        }
        logger.info(
            "Verifier {}/{}: is_contradiction={} type={} explanation={!r}",
            idx + 1, total, is_contra, contra_type, (explanation or "")[:200],
        )
