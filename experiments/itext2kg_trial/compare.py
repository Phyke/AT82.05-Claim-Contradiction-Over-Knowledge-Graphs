"""
Compare naive (notebook 02) vs iText2KG triple extraction on the same documents.

Reads:
  - ../data/processed/ContraDoc/triples.jsonl  (naive, all 100 docs)
  - smoke_output.json                          (iText2KG, currently 1 doc)

Reports six "student-invented" metrics on the doc overlap:
  Atomicity:        mean tokens per s/p/o, compound-object rate
  Canonicalization: predicate vocab, predicate reuse, subject vocab, entity vocab
  Argument quality: pronoun-as-argument rate, noun/verb POS purity (spaCy)
  Pipeline lift:    gold-pair predicate Jaccard (RQ1 signal)
"""

import json
from collections import Counter
from pathlib import Path

NAIVE_PATH = Path(__file__).parent.parent / "data" / "processed" / "ContraDoc" / "triples.jsonl"
ITEXT2KG_PATH = Path(__file__).parent / "triples_v2.jsonl"
ITEXT2KG_FALLBACK = Path(__file__).parent / "smoke_output.json"  # falls back if multi-doc not yet run

PRONOUNS = {
    "he", "she", "it", "they", "we", "i", "you",
    "him", "her", "them", "us", "me",
    "his", "hers", "its", "their", "our", "your", "my",
    "this", "that", "these", "those",
}

try:
    import spacy
    NLP = spacy.load("en_core_web_sm", disable=["parser", "ner", "lemmatizer"])
except (ImportError, OSError):
    NLP = None


def load_naive() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Returns (triples_by_doc, gold_by_doc).
    triples_by_doc[doc_id] = list of {s, p, o, sentence_id}.
    gold_by_doc[doc_id] = {gold_evidence_sentence_id, gold_ref_sentence_ids} for YES docs."""
    triples_by_doc: dict[str, list[dict]] = {}
    gold_by_doc: dict[str, dict] = {}
    for line in NAIVE_PATH.open(encoding="utf-8"):
        rec = json.loads(line)
        flat = []
        for sent in rec["sentences"]:
            for t in sent["triples"]:
                flat.append(
                    {"s": t["s"], "p": t["p"], "o": t["o"], "sentence_id": sent["sentence_id"]}
                )
        triples_by_doc[rec["doc_id"]] = flat
        if rec["contradiction"] == "YES":
            gold_by_doc[rec["doc_id"]] = {
                "evidence": rec.get("gold_evidence_sentence_id"),
                "refs": rec.get("gold_ref_sentence_ids", []),
            }
    return triples_by_doc, gold_by_doc


def load_itext2kg() -> tuple[dict[str, list[dict]], dict[str, str]]:
    """Returns (triples_by_doc, doc_type_by_doc).
    Reads triples_v2.jsonl if present, else falls back to single-doc smoke_output.json."""
    triples_by_doc: dict[str, list[dict]] = {}
    doc_type: dict[str, str] = {}
    if ITEXT2KG_PATH.exists():
        for line in ITEXT2KG_PATH.open(encoding="utf-8"):
            rec = json.loads(line)
            flat = []
            for sent in rec["per_sentence"]:
                for t in sent["triples"]:
                    flat.append(
                        {"s": t["s"], "p": t["p"], "o": t["o"], "sentence_id": sent["sentence_id"]}
                    )
            triples_by_doc[rec["doc_id"]] = flat
            doc_type[rec["doc_id"]] = rec.get("doc_type", "unknown")
    elif ITEXT2KG_FALLBACK.exists():
        rec = json.loads(ITEXT2KG_FALLBACK.read_text(encoding="utf-8"))
        flat = []
        for sent in rec["per_sentence"]:
            for t in sent["triples"]:
                flat.append(
                    {"s": t["s"], "p": t["p"], "o": t["o"], "sentence_id": sent["sentence_id"]}
                )
        triples_by_doc[rec["doc_id"]] = flat
        doc_type[rec["doc_id"]] = "unknown"
    return triples_by_doc, doc_type


def tokens(text: str) -> list[str]:
    return text.split()


def pos_purity(text: str, target: set[str]) -> float | None:
    if NLP is None:
        return None
    doc = NLP(text)
    toks = [t for t in doc if not t.is_punct and not t.is_space]
    if not toks:
        return None
    return sum(1 for t in toks if t.pos_ in target) / len(toks)


def metrics(triples: list[dict]) -> dict:
    if not triples:
        return {"n_triples": 0}
    n = len(triples)

    s_lens = [len(tokens(t["s"])) for t in triples]
    p_lens = [len(tokens(t["p"])) for t in triples]
    o_lens = [len(tokens(t["o"])) for t in triples]

    preds = [t["p"].strip().lower() for t in triples]
    subjs = [t["s"].strip().lower() for t in triples]
    objs = [t["o"].strip().lower() for t in triples]
    pred_vocab = len(set(preds))
    subj_vocab = len(set(subjs))
    ent_vocab = len(set(subjs) | set(objs))

    pronoun_rate = sum(
        1 for t in triples
        if t["s"].strip().lower() in PRONOUNS or t["o"].strip().lower() in PRONOUNS
    ) / n

    s_noun = [pos_purity(t["s"], {"NOUN", "PROPN"}) for t in triples]
    o_noun = [pos_purity(t["o"], {"NOUN", "PROPN"}) for t in triples]
    p_verb = [pos_purity(t["p"], {"VERB", "AUX"}) for t in triples]
    s_noun = [x for x in s_noun if x is not None]
    o_noun = [x for x in o_noun if x is not None]
    p_verb = [x for x in p_verb if x is not None]

    return {
        "n_triples": n,
        "mean_s_tokens": sum(s_lens) / n,
        "mean_p_tokens": sum(p_lens) / n,
        "mean_o_tokens": sum(o_lens) / n,
        "compound_o_rate": sum(1 for L in o_lens if L > 4) / n,
        "pred_vocab": pred_vocab,
        "pred_reuse": n / pred_vocab,
        "subj_vocab": subj_vocab,
        "ent_vocab": ent_vocab,
        "pronoun_rate": pronoun_rate,
        "mean_s_noun_purity": sum(s_noun) / len(s_noun) if s_noun else None,
        "mean_o_noun_purity": sum(o_noun) / len(o_noun) if o_noun else None,
        "mean_p_verb_purity": sum(p_verb) / len(p_verb) if p_verb else None,
        "top_predicates": Counter(preds).most_common(5),
    }


def gold_pair_jaccard(triples: list[dict], gold: dict) -> float | None:
    ev_sid = gold.get("evidence")
    ref_sids = set(gold.get("refs", []))
    if ev_sid is None or not ref_sids:
        return None
    ev_preds = {t["p"].strip().lower() for t in triples if t["sentence_id"] == ev_sid}
    ref_preds = {t["p"].strip().lower() for t in triples if t["sentence_id"] in ref_sids}
    if not ev_preds and not ref_preds:
        return None
    if not ev_preds or not ref_preds:
        return 0.0
    return len(ev_preds & ref_preds) / len(ev_preds | ref_preds)


def fmt(x):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.3f}"
    if isinstance(x, list):
        return str(x)
    return str(x)


def main():
    naive, gold = load_naive()
    itext, doc_types = load_itext2kg()

    overlap = sorted(set(naive.keys()) & set(itext.keys()))
    print(f"Naive: {len(naive)} docs   iText2KG: {len(itext)} docs   overlap: {len(overlap)}")
    print(f"spaCy POS purity: {'enabled' if NLP else 'disabled'}")
    print()

    naive_all = [t for d in overlap for t in naive[d]]
    itext_all = [t for d in overlap for t in itext[d]]
    n = metrics(naive_all)
    i = metrics(itext_all)

    rows = [
        ("Atomicity",        "Total triples",                "n_triples",          "lower-not-better"),
        ("",                 "Mean tokens (subject)",        "mean_s_tokens",      "lower=more atomic"),
        ("",                 "Mean tokens (predicate)",      "mean_p_tokens",      "lower=more atomic"),
        ("",                 "Mean tokens (object)",         "mean_o_tokens",      "lower=more atomic"),
        ("",                 "Compound-object rate (>4 tok)","compound_o_rate",    "lower=more atomic"),
        ("Canonicalization", "Predicate vocabulary",         "pred_vocab",         "lower=more canonical"),
        ("",                 "Predicate reuse (n/vocab)",    "pred_reuse",         "higher=more canonical"),
        ("",                 "Subject vocabulary",           "subj_vocab",         "lower=more entity merging"),
        ("",                 "Entity vocabulary (s ∪ o)",    "ent_vocab",          "lower=more entity merging"),
        ("Argument quality", "Pronoun-as-argument rate",     "pronoun_rate",       "lower=cleaner args"),
        ("",                 "Subject noun-purity (POS)",    "mean_s_noun_purity", "higher=well-formed"),
        ("",                 "Object noun-purity (POS)",     "mean_o_noun_purity", "higher=well-formed"),
        ("",                 "Predicate verb-purity (POS)",  "mean_p_verb_purity", "higher=well-formed"),
    ]

    print(f"{'Section':<18}  {'Metric':<33}  {'Naive':>10}  {'iText2KG':>10}  {'Direction':<24}")
    print("-" * 105)
    for section, label, key, direction in rows:
        nv = fmt(n.get(key))
        iv = fmt(i.get(key))
        winner = ""
        if isinstance(n.get(key), (int, float)) and isinstance(i.get(key), (int, float)):
            n_better = (
                (("lower" in direction) and n[key] < i[key])
                or (("higher" in direction) and n[key] > i[key])
            )
            i_better = (
                (("lower" in direction) and i[key] < n[key])
                or (("higher" in direction) and i[key] > n[key])
            )
            if n_better:
                nv = nv + "*"
            elif i_better:
                iv = iv + "*"
        print(f"{section:<18}  {label:<33}  {nv:>10}  {iv:>10}  {direction:<24}")

    print()
    print("Top 5 most common predicates per system (overlap docs):")
    print(f"  Naive:    {n.get('top_predicates')}")
    print(f"  iText2KG: {i.get('top_predicates')}")

    print()
    print("Gold-pair predicate Jaccard (RQ1-relevant; per-doc, YES docs only)")
    print("-" * 70)
    print(f"  {'doc_id':<25}  {'Naive':>8}  {'iText2KG':>10}  {'Δ':>8}")
    n_jac_vals = []
    i_jac_vals = []
    for doc_id in overlap:
        if doc_id not in gold:
            continue
        nj = gold_pair_jaccard(naive[doc_id], gold[doc_id])
        ij = gold_pair_jaccard(itext[doc_id], gold[doc_id])
        if nj is not None:
            n_jac_vals.append(nj)
        if ij is not None:
            i_jac_vals.append(ij)
        delta = (ij - nj) if (nj is not None and ij is not None) else None
        print(f"  {doc_id:<25}  {fmt(nj):>8}  {fmt(ij):>10}  {fmt(delta):>8}")
    if n_jac_vals or i_jac_vals:
        n_mean = sum(n_jac_vals) / len(n_jac_vals) if n_jac_vals else None
        i_mean = sum(i_jac_vals) / len(i_jac_vals) if i_jac_vals else None
        print(f"  {'mean':<25}  {fmt(n_mean):>8}  {fmt(i_mean):>10}")


if __name__ == "__main__":
    main()
