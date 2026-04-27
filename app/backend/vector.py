import numpy as np


def top_k_pairs(sentence_ids: list[int], embeddings: np.ndarray, k: int) -> list[tuple[int, int, float]]:
    """Return up to k highest-cosine pairs sorted desc. Embeddings assumed L2-normalized."""
    n = len(sentence_ids)
    if n < 2:
        return []
    sim = embeddings @ embeddings.T
    scored: list[tuple[int, int, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            scored.append((sentence_ids[i], sentence_ids[j], float(sim[i, j])))
    scored.sort(key=lambda x: -x[2])
    return scored[:k]
